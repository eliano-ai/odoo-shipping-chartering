# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

STATE = [
    ('draft', 'Draft'),
    ('fixed', 'Fixed'),
    ('sailing', 'Sailing'),
    ('at_port', 'At Port'),
    ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
]


class VesselVoyage(models.Model):
    _name = 'vessel.voyage'
    _description = 'Voyage — Pelayaran Fisik Kapal'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_departure desc, id desc'

    name = fields.Char(
        string='Nomor Voyage', readonly=True, copy=False,
        default=lambda self: _('New'),
    )
    charter_contract_id = fields.Many2one(
        'vessel.charter.contract', string='Kontrak Charter',
        domain=[('state', 'in', ('confirmed', 'in_progress'))],
        tracking=True,
    )
    vessel_id = fields.Many2one(
        'fleet.vehicle', string='Kapal',
        related='charter_contract_id.vessel_id', store=True, readonly=True,
    )
    tug_id = fields.Many2one(
        'fleet.vehicle', string='Kapal Tunda (Tug)',
        related='charter_contract_id.tug_id', store=True, readonly=True,
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account (Voyage)',
        related='charter_contract_id.analytic_account_id', store=True, readonly=True,
    )
    fleet_trip_id = fields.Many2one(
        'fleet.vehicle.trip', string='Fleet Trip (Fuel Log)',
        help='Bridge opsional ke fleet_fuel_log untuk korelasi konsumsi BBM per voyage. '
             'Modul vessel_voyage_operations tidak hard-depend ke fleet_fuel_log — field ini '
             'diasumsikan aman karena fleet_fuel_log selalu terinstall di environment project ini '
             '(Layer 1). Instalasi tanpa fleet_fuel_log butuh bridge module terpisah (di luar scope MVP).',
    )
    date_departure = fields.Datetime(string='Tanggal Berangkat (Aktual)', tracking=True)
    date_arrival_final = fields.Datetime(string='Tanggal Tiba Final (Aktual)', tracking=True)
    origin_port_id = fields.Many2one(
        'res.partner', string='Port Asal', domain=[('is_port', '=', True)],
    )
    final_port_id = fields.Many2one(
        'res.partner', string='Port Tujuan Final', domain=[('is_port', '=', True)],
    )
    total_distance_nm = fields.Float(
        string='Total Jarak (NM)', compute='_compute_total_distance_nm', store=True,
    )
    total_delay_hours = fields.Float(
        string='Total Delay (jam)', compute='_compute_total_delay_hours', store=True,
    )
    state = fields.Selection(
        STATE, string='Status',
        default='draft', required=True, tracking=True, copy=False, index=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Perusahaan', required=True,
        default=lambda self: self.env.company,
    )
    user_id = fields.Many2one(
        'res.users', string='Operations',
        default=lambda self: self.env.user,
    )

    # ─────────────────────────────────────────────────────────────────────
    # Compute — placeholder, diisi data riil setelah model terkait ada
    # ─────────────────────────────────────────────────────────────────────

    @api.depends('state')
    def _compute_total_distance_nm(self):
        # Placeholder — akan depend ke noon_report_ids.distance_run_nm setelah
        # vessel.noon.report ada (Sprint 11).
        for rec in self:
            rec.total_distance_nm = 0.0

    @api.depends('state')
    def _compute_total_delay_hours(self):
        # Placeholder — akan depend ke delay_event_ids.duration_hours setelah
        # vessel.voyage.delay ada (Sprint 13).
        for rec in self:
            rec.total_delay_hours = 0.0

    # ─────────────────────────────────────────────────────────────────────
    # Constraints
    # ─────────────────────────────────────────────────────────────────────

    @api.constrains('date_departure', 'date_arrival_final')
    def _check_dates(self):
        for rec in self:
            if rec.date_departure and rec.date_arrival_final \
                    and rec.date_arrival_final < rec.date_departure:
                raise ValidationError(_(
                    'Tanggal tiba final tidak boleh sebelum tanggal berangkat.'
                ))

    @api.constrains('charter_contract_id', 'state', 'date_departure', 'date_arrival_final')
    def _check_one_active_voyage_per_contract(self):
        for rec in self:
            if not rec.charter_contract_id or rec.state in ('completed', 'cancelled'):
                continue
            domain = [
                ('charter_contract_id', '=', rec.charter_contract_id.id),
                ('id', '!=', rec.id),
                ('state', 'not in', ('completed', 'cancelled')),
            ]
            others = self.search(domain)
            if not others:
                continue
            if rec.charter_contract_id.contract_type == 'time':
                # Time charter boleh >1 voyage berurutan, asal tidak overlap tanggal.
                end_a = rec.date_arrival_final or rec.date_departure
                for other in others:
                    if not rec.date_departure or not other.date_departure:
                        continue
                    end_b = other.date_arrival_final or other.date_departure
                    if end_a and rec.date_departure <= end_b and other.date_departure <= end_a:
                        raise ValidationError(_(
                            'Voyage ini beririsan tanggal dengan voyage lain (%s) '
                            'pada kontrak time charter yang sama.'
                        ) % other.name)
                continue
            raise ValidationError(_(
                'Kontrak %(contract)s sudah punya voyage aktif (%(other)s). '
                'Satu kontrak voyage/COA hanya boleh punya 1 voyage aktif.'
            ) % {'contract': rec.charter_contract_id.name, 'other': others[0].name})

    # ─────────────────────────────────────────────────────────────────────
    # ORM overrides
    # ─────────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('vessel.voyage') or _('New')
        return super().create(vals_list)

    # ─────────────────────────────────────────────────────────────────────
    # State machine
    # ─────────────────────────────────────────────────────────────────────

    def action_fix(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Hanya voyage Draft yang bisa di-fix.'))
            if not rec.charter_contract_id:
                raise UserError(_('Kontrak charter wajib dipilih sebelum voyage di-fix.'))
            if not rec.charter_contract_id.vessel_id:
                raise ValidationError(_(
                    'Kontrak %s belum punya kapal — tidak bisa fix voyage.'
                ) % rec.charter_contract_id.name)
            rec.state = 'fixed'
            rec.message_post(body=_('Voyage di-fix dari kontrak %s.') % rec.charter_contract_id.name)

    def action_depart(self):
        for rec in self:
            if rec.state != 'fixed':
                raise UserError(_('Hanya voyage Fixed yang bisa berangkat.'))
            if not rec.origin_port_id:
                raise ValidationError(_('Port asal wajib diisi sebelum voyage berangkat.'))
            if not rec.date_departure:
                rec.date_departure = fields.Datetime.now()
            rec.state = 'sailing'
            rec.message_post(body=_('Voyage berangkat dari %s.') % rec.origin_port_id.name)

    def action_arrive_port(self):
        """Toggle sailing -> at_port. Logic penuh terhubung port_call_ids (atb/atd)
        di Sprint 10 — untuk sprint ini implementasi dasar transisi state saja."""
        for rec in self:
            if rec.state != 'sailing':
                raise UserError(_('Hanya voyage Sailing yang bisa tiba di port.'))
            rec.state = 'at_port'
            rec.message_post(body=_('Voyage tiba di port.'))

    def action_depart_port(self):
        """Toggle at_port -> sailing. Lihat catatan action_arrive_port."""
        for rec in self:
            if rec.state != 'at_port':
                raise UserError(_('Hanya voyage At Port yang bisa berangkat lagi.'))
            rec.state = 'sailing'
            rec.message_post(body=_('Voyage berangkat lagi dari port.'))

    def action_complete(self):
        for rec in self:
            if rec.state not in ('sailing', 'at_port'):
                raise UserError(_('Hanya voyage Sailing/At Port yang bisa diselesaikan.'))
            # TODO(Sprint 12): validasi minimal 1 cargo_document_ids type=bl untuk voyage
            # charter — cargo_document_ids belum ada model-nya sampai Sprint 12.
            if not rec.date_arrival_final:
                rec.date_arrival_final = fields.Datetime.now()
            rec.state = 'completed'
            rec.message_post(body=_('Voyage selesai (completed).'))

    def action_cancel(self):
        self.ensure_one()
        if self.state not in ('draft', 'fixed'):
            raise UserError(_(
                'Hanya voyage Draft/Fixed yang bisa dibatalkan.'
            ))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Batalkan Voyage'),
            'res_model': 'vessel.voyage.cancel.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_voyage_id': self.id},
        }

    def action_reset_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_('Hanya voyage Cancelled yang bisa dikembalikan ke Draft.'))
            rec.state = 'draft'
