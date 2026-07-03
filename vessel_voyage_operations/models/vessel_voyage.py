# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

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
    port_call_ids = fields.One2many(
        'vessel.port.call', 'voyage_id', string='Port Rotation',
    )
    noon_report_ids = fields.One2many(
        'vessel.noon.report', 'voyage_id', string='Noon Reports',
    )
    cargo_document_ids = fields.One2many(
        'vessel.cargo.document', 'voyage_id', string='Cargo Documents',
    )
    delay_event_ids = fields.One2many(
        'vessel.voyage.delay', 'voyage_id', string='Delay Log',
    )
    assigned_user_ids = fields.Many2many(
        'res.users', compute='_compute_assigned_user_ids', store=True,
        string='User Bertugas (Crew On Board)',
        help='Dipakai record rule portal Nakhoda — user account dari vessel.seafarer '
             'yang sedang on_board di kapal voyage ini. Bridge opsional ke '
             'vessel_crew_management (soft dependency, pola sama seperti fleet_trip_id) — '
             'diasumsikan aman karena vessel_crew_management selalu terinstall di '
             'environment project ini (Layer 1).',
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
    noon_report_count = fields.Integer(string='Jumlah Noon Report', compute='_compute_noon_report_count')
    port_call_count = fields.Integer(string='Jumlah Port Call', compute='_compute_port_call_count')
    cargo_document_count = fields.Integer(string='Jumlah Cargo Document', compute='_compute_cargo_document_count')
    delay_count = fields.Integer(string='Jumlah Delay', compute='_compute_delay_count')

    # ─────────────────────────────────────────────────────────────────────
    # Compute — placeholder, diisi data riil setelah model terkait ada
    # ─────────────────────────────────────────────────────────────────────

    @api.depends('noon_report_ids.distance_run_nm', 'noon_report_ids.state')
    def _compute_total_distance_nm(self):
        for rec in self:
            approved = rec.noon_report_ids.filtered(lambda r: r.state == 'approved')
            rec.total_distance_nm = sum(approved.mapped('distance_run_nm'))

    @api.depends('noon_report_ids')
    def _compute_noon_report_count(self):
        for rec in self:
            rec.noon_report_count = len(rec.noon_report_ids)

    @api.depends('port_call_ids')
    def _compute_port_call_count(self):
        for rec in self:
            rec.port_call_count = len(rec.port_call_ids)

    @api.depends('cargo_document_ids')
    def _compute_cargo_document_count(self):
        for rec in self:
            rec.cargo_document_count = len(rec.cargo_document_ids)

    @api.depends('delay_event_ids')
    def _compute_delay_count(self):
        for rec in self:
            rec.delay_count = len(rec.delay_event_ids)

    @api.depends('delay_event_ids.duration_hours')
    def _compute_total_delay_hours(self):
        for rec in self:
            rec.total_delay_hours = sum(rec.delay_event_ids.mapped('duration_hours'))

    # Technical debt (sama kelas dengan fleet_trip_id, Sprint 9): depends menyentuh
    # field dari vessel_crew_management (soft dependency, tidak di manifest depends).
    # Aman selama vessel_crew_management selalu terinstall di environment project ini
    # (Layer 1) — di environment tanpa modul itu, resolve_depends() akan gagal saat
    # registry setup (bukan silent, error jelas saat install).
    @api.depends('vessel_id.crew_assignment_ids.state',
                 'vessel_id.crew_assignment_ids.seafarer_id.employee_id.user_id')
    def _compute_assigned_user_ids(self):
        for rec in self:
            if not rec.vessel_id:
                rec.assigned_user_ids = [(5, 0, 0)]
                continue
            on_board = rec.vessel_id.crew_assignment_ids.filtered(lambda a: a.state == 'on_board')
            users = on_board.mapped('seafarer_id.employee_id.user_id')
            rec.assigned_user_ids = [(6, 0, users.ids)]

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
            rec._send_voyage_fixed_email()

    def _send_voyage_fixed_email(self):
        self.ensure_one()
        template = self.env.ref(
            'vessel_voyage_operations.email_template_voyage_fixed', raise_if_not_found=False,
        )
        if template and self.user_id and self.user_id.email:
            try:
                template.send_mail(self.id, force_send=True, raise_exception=False)
            except Exception as e:
                _logger.warning('Gagal kirim email voyage fixed untuk %s: %s', self.name, e)

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
        """Toggle sailing -> at_port. Isi atb di port_call_ids aktif (baris urutan
        terkecil yang belum punya atb)."""
        for rec in self:
            if rec.state != 'sailing':
                raise UserError(_('Hanya voyage Sailing yang bisa tiba di port.'))
            next_call = rec.port_call_ids.filtered(lambda c: not c.atb).sorted('sequence')[:1]
            if not next_call:
                raise UserError(_(
                    'Tidak ada port call berikutnya yang terjadwal (semua port_call_ids '
                    'sudah punya ATB, atau belum ada port call sama sekali).'
                ))
            if not next_call.ata:
                next_call.ata = fields.Datetime.now()
            next_call.atb = fields.Datetime.now()
            rec.state = 'at_port'
            rec.message_post(body=_('Voyage tiba di port %s.') % next_call.port_id.display_name)

    def action_depart_port(self):
        """Toggle at_port -> sailing. Isi atd di port_call_ids yang sedang aktif
        (baris dengan atb terisi tapi atd belum)."""
        for rec in self:
            if rec.state != 'at_port':
                raise UserError(_('Hanya voyage At Port yang bisa berangkat lagi.'))
            current_call = rec.port_call_ids.filtered(
                lambda c: c.atb and not c.atd
            ).sorted('sequence')[:1]
            if not current_call:
                raise UserError(_(
                    'Tidak ditemukan port call aktif (dengan ATB terisi, ATD kosong) '
                    'untuk voyage ini.'
                ))
            current_call.atd = fields.Datetime.now()
            rec.state = 'sailing'
            rec.message_post(body=_('Voyage berangkat lagi dari port %s.') % current_call.port_id.display_name)

    def action_complete(self):
        for rec in self:
            if rec.state not in ('sailing', 'at_port'):
                raise UserError(_('Hanya voyage Sailing/At Port yang bisa diselesaikan.'))
            calls = rec.port_call_ids.sorted('sequence')
            if calls:
                for call in calls[:-1]:
                    if not call.atd:
                        raise ValidationError(_(
                            'Port call %s belum punya ATD — voyage tidak bisa diselesaikan '
                            'selama masih ada port singgah (bukan tujuan final) yang belum '
                            'berangkat.'
                        ) % call.port_id.display_name)
                last_call = calls[-1]
                if not last_call.atb:
                    raise ValidationError(_(
                        'Port call tujuan final (%s) belum punya ATB — voyage tidak bisa '
                        'diselesaikan.'
                    ) % last_call.port_id.display_name)
            if rec.charter_contract_id.contract_type == 'voyage' \
                    and not rec.cargo_document_ids.filtered(lambda d: d.document_type == 'bl'):
                raise ValidationError(_(
                    'Voyage charter wajib punya minimal 1 cargo document tipe Bill of '
                    'Lading sebelum diselesaikan.'
                ))
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

    def action_view_noon_reports(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Noon Reports — %s') % self.name,
            'res_model': 'vessel.noon.report',
            'view_mode': 'list,form',
            'domain': [('voyage_id', '=', self.id)],
            'context': {'default_voyage_id': self.id},
        }

    def action_view_port_calls(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Port Calls — %s') % self.name,
            'res_model': 'vessel.port.call',
            'view_mode': 'list,calendar,form',
            'domain': [('voyage_id', '=', self.id)],
            'context': {'default_voyage_id': self.id},
        }

    def action_view_cargo_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cargo Documents — %s') % self.name,
            'res_model': 'vessel.cargo.document',
            'view_mode': 'list,form',
            'domain': [('voyage_id', '=', self.id)],
            'context': {'default_voyage_id': self.id},
        }

    def action_view_delays(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Delay Log — %s') % self.name,
            'res_model': 'vessel.voyage.delay',
            'view_mode': 'list,form',
            'domain': [('voyage_id', '=', self.id)],
            'context': {'default_voyage_id': self.id},
        }

    def action_view_charter_contract(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.charter_contract_id.name,
            'res_model': 'vessel.charter.contract',
            'view_mode': 'form',
            'res_id': self.charter_contract_id.id,
            'target': 'current',
        }

    # ─────────────────────────────────────────────────────────────────────
    # Cron Jobs — Sprint 13
    # ─────────────────────────────────────────────────────────────────────

    @api.model
    def _cron_noon_report_missing_alert(self):
        """Harian — voyage sailing/at_port tanpa noon report approved 30 jam terakhir."""
        cutoff = fields.Datetime.now() - timedelta(hours=30)
        voyages = self.search([('state', 'in', ('sailing', 'at_port'))])
        for voyage in voyages:
            last_approved = voyage.noon_report_ids.filtered(
                lambda r: r.state == 'approved'
            ).sorted('report_datetime', reverse=True)[:1]
            if last_approved and last_approved.report_datetime >= cutoff:
                continue
            existing = self.env['mail.activity'].search([
                ('res_model', '=', 'vessel.voyage'),
                ('res_id', '=', voyage.id),
                ('summary', 'like', 'Noon report belum ada'),
            ])
            if existing:
                continue
            voyage.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Noon report belum ada dalam 30 jam terakhir — %s') % voyage.name,
                note=_(
                    'Voyage %(name)s (status %(state)s) belum ada noon report approved '
                    'dalam 30 jam terakhir. Cek kondisi kapal/koordinasi dengan Nakhoda.'
                ) % {'name': voyage.name, 'state': voyage.state},
                user_id=voyage.user_id.id or self.env.uid,
            )
