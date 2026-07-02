from odoo import api, fields, models, _
from datetime import timedelta


class VesselCrewSchedule(models.Model):
    """
    Rotation schedule: rencana kapan ABK on board vs on leave.
    Berbeda dari vessel.crew.assignment (yang mencatat aktual),
    ini adalah planning tool + integrasi Calendar Odoo.
    """
    _name = 'vessel.crew.schedule'
    _description = 'Jadwal Rotasi Crew Kapal'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc'

    name = fields.Char(
        string='Nama Jadwal', compute='_compute_name', store=True,
    )
    seafarer_id = fields.Many2one(
        'vessel.seafarer', string='ABK', required=True,
        tracking=True, index=True,
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Kapal', required=True,
        domain=[('is_vessel', '=', True)], tracking=True,
    )
    rank_id = fields.Many2one(
        'vessel.crew.rank', string='Jabatan', required=True,
    )
    start_date = fields.Date(
        string='Tanggal Mulai (Sign On)', required=True, tracking=True,
    )
    end_date = fields.Date(
        string='Tanggal Selesai (Sign Off)', required=True, tracking=True,
    )
    schedule_type = fields.Selection([
        ('on_board', 'On Board (Bertugas)'),
        ('leave', 'Cuti / Off'),
        ('training', 'Pelatihan'),
        ('standby', 'Standby'),
    ], string='Tipe Jadwal', default='on_board', required=True)
    port = fields.Char(string='Pelabuhan')
    notes = fields.Text(string='Catatan')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Selesai'),
    ], default='draft', tracking=True)

    # ── Link ke Odoo Calendar ──────────────────────────────────────────────
    calendar_event_id = fields.Many2one(
        'calendar.event', string='Event Kalender',
        readonly=True, copy=False,
    )
    create_calendar_event = fields.Boolean(
        string='Buat di Kalender Odoo', default=True,
    )

    # ── Link ke Assignment ─────────────────────────────────────────────────
    assignment_id = fields.Many2one(
        'vessel.crew.assignment', string='Assignment Terkait',
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company,
    )

    @api.depends('seafarer_id', 'vehicle_id', 'start_date', 'schedule_type')
    def _compute_name(self):
        type_label = {
            'on_board': 'On Board',
            'leave': 'Cuti',
            'training': 'Training',
            'standby': 'Standby',
        }
        for rec in self:
            parts = [
                rec.seafarer_id.name or '',
                rec.vehicle_id.name or '' if rec.vehicle_id else '',
                type_label.get(rec.schedule_type, ''),
                str(rec.start_date) if rec.start_date else '',
            ]
            rec.name = ' · '.join(filter(None, parts))

    def action_confirm(self):
        for rec in self:
            rec.write({'state': 'confirmed'})
            if rec.create_calendar_event and not rec.calendar_event_id:
                rec._create_calendar_event()

    def _create_calendar_event(self):
        """Create/update Odoo Calendar event for this schedule."""
        self.ensure_one()
        partner = self.seafarer_id.employee_id.user_id.partner_id
        type_emoji = {
            'on_board': '🚢',
            'leave': '🏖',
            'training': '📚',
            'standby': '⏳',
        }
        name = (
            f"{type_emoji.get(self.schedule_type, '')} "
            f"{self.seafarer_id.name} — {self.vehicle_id.name} "
            f"({dict(self._fields['schedule_type'].selection).get(self.schedule_type, '')})"
        )
        vals = {
            'name': name,
            'start': fields.Datetime.from_string(f"{self.start_date} 07:00:00"),
            'stop': fields.Datetime.from_string(f"{self.end_date} 17:00:00"),
            'allday': True,
            'description': (
                f"Kapal: {self.vehicle_id.name}\n"
                f"Jabatan: {self.rank_id.name}\n"
                f"Pelabuhan: {self.port or '-'}\n"
                f"Catatan: {self.notes or '-'}"
            ),
            'partner_ids': [(4, partner.id)] if partner else [],
        }
        event = self.env['calendar.event'].create(vals)
        self.calendar_event_id = event

    def action_create_assignment(self):
        """Create a vessel.crew.assignment from this schedule."""
        self.ensure_one()
        if self.assignment_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'vessel.crew.assignment',
                'res_id': self.assignment_id.id,
                'view_mode': 'form',
            }
        assignment = self.env['vessel.crew.assignment'].create({
            'vehicle_id': self.vehicle_id.id,
            'seafarer_id': self.seafarer_id.id,
            'rank_id': self.rank_id.id,
            'sign_on_date': self.start_date,
            'sign_off_date': self.end_date,
            'sign_on_port': self.port or '',
        })
        self.assignment_id = assignment
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'vessel.crew.assignment',
            'res_id': assignment.id,
            'view_mode': 'form',
        }
