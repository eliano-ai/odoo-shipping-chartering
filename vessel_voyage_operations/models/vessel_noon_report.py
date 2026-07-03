# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

# Odoo 19: `_sql_constraints = [...]` (list attribute) tidak lagi berfungsi (silent
# no-op, tidak ada error/warning) — diganti `models.Constraint(...)` per-atribut.
# Ditemukan via test unit yang gagal karena constraint DB ternyata tidak pernah
# ter-apply meski model.py "kelihatan benar" (lihat CLAUDE.md Checklist Odoo 19 Gotcha).

REPORT_TYPE = [
    ('noon_at_sea', 'Noon at Sea'),
    ('noon_in_port', 'Noon in Port'),
    ('arrival', 'Arrival'),
    ('departure', 'Departure'),
    ('sosp_eosp', 'SOSP/EOSP'),
]

SEA_STATE = [
    ('calm', 'Calm'),
    ('slight', 'Slight'),
    ('moderate', 'Moderate'),
    ('rough', 'Rough'),
    ('very_rough', 'Very Rough'),
]

STATE = [
    ('draft', 'Draft'),
    ('submitted', 'Submitted'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]

SOURCE = [
    ('portal', 'Portal'),
    ('manual', 'Manual'),
    ('email_parsed', 'Email Parsed'),
]


class VesselNoonReport(models.Model):
    _name = 'vessel.noon.report'
    _description = 'Noon Report / Daily Position Report'
    _inherit = ['mail.thread']
    _order = 'report_datetime desc'

    voyage_id = fields.Many2one(
        'vessel.voyage', string='Voyage', required=True, ondelete='cascade',
    )
    report_datetime = fields.Datetime(string='Waktu Laporan', required=True)
    report_type = fields.Selection(REPORT_TYPE, string='Tipe Laporan', default='noon_at_sea')
    latitude = fields.Float(string='Latitude', digits=(10, 6))
    longitude = fields.Float(string='Longitude', digits=(10, 6))
    course_deg = fields.Float(string='Course (derajat)')
    speed_knots = fields.Float(string='Speed (knots)')
    distance_run_nm = fields.Float(string='Distance Run 24h (NM)')
    distance_to_go_nm = fields.Float(string='Distance to Go (NM)')
    rob_fo = fields.Float(string='ROB FO (MT)')
    rob_do = fields.Float(string='ROB DO (MT)')
    rob_fw = fields.Float(string='ROB FW (KL)')
    rob_lube_oil = fields.Float(string='ROB Lube Oil (KL)')
    wind_force_bft = fields.Integer(string='Wind Force (Beaufort)')
    sea_state = fields.Selection(SEA_STATE, string='Sea State')
    rpm = fields.Float(string='RPM')
    slip_pct = fields.Float(string='Slip (%)')
    state = fields.Selection(
        STATE, string='Status', default='draft', required=True, tracking=True, copy=False,
    )
    approved_by = fields.Many2one('res.users', string='Disetujui Oleh', readonly=True, copy=False)
    approved_date = fields.Datetime(string='Tanggal Disetujui', readonly=True, copy=False)
    rejection_reason = fields.Char(string='Alasan Penolakan', copy=False)
    source = fields.Selection(SOURCE, string='Sumber', default='manual', required=True)
    company_id = fields.Many2one(
        related='voyage_id.company_id', string='Perusahaan', store=True, readonly=True,
    )

    _uniq_voyage_datetime = models.Constraint(
        'unique(voyage_id, report_datetime)',
        'Noon report untuk voyage & waktu yang sama sudah ada.',
    )

    @api.constrains('latitude', 'longitude')
    def _check_lat_long_range(self):
        for rec in self:
            if rec.latitude and not (-90 <= rec.latitude <= 90):
                raise ValidationError(_('Latitude harus di antara -90 dan 90.'))
            if rec.longitude and not (-180 <= rec.longitude <= 180):
                raise ValidationError(_('Longitude harus di antara -180 dan 180.'))

    # ─────────────────────────────────────────────────────────────────────
    # Workflow — approved/rejected read-only ditegakkan di level view
    # (readonly="state in ('approved', 'rejected')"), bukan override write()
    # model-level — pola sama seperti vessel.charter.contract/vessel.laytime.calculation
    # di vessel_chartering, supaya tidak memblokir write() dari ORM data loader
    # (XML noupdate="0" re-write field yang sama saat -u idempotency check).
    # ─────────────────────────────────────────────────────────────────────

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Hanya noon report Draft yang bisa disubmit.'))
            rec.state = 'submitted'

    def action_approve(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Hanya noon report Submitted yang bisa diapprove.'))
            rec._check_gap_warning()
            rec._check_rob_bunkering_warning()
            rec.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })

    def action_reject(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Hanya noon report Submitted yang bisa direject.'))
            if not rec.rejection_reason:
                raise ValidationError(_('Alasan penolakan wajib diisi.'))
            rec.write({'state': 'rejected'})

    def _check_gap_warning(self):
        """Warning (bukan blokir) kalau gap dengan noon report approved sebelumnya > 30 jam."""
        self.ensure_one()
        previous = self.search([
            ('voyage_id', '=', self.voyage_id.id),
            ('state', '=', 'approved'),
            ('report_datetime', '<', self.report_datetime),
        ], order='report_datetime desc', limit=1)
        if not previous:
            return
        gap_hours = (self.report_datetime - previous.report_datetime).total_seconds() / 3600.0
        if gap_hours > 30:
            self.voyage_id.message_post(body=_(
                '⚠️ Peringatan: gap %(gap).1f jam antara noon report %(prev)s dan %(curr)s '
                '(indikasi ada laporan terlewat).'
            ) % {'gap': gap_hours, 'prev': previous.report_datetime, 'curr': self.report_datetime})

    def _check_rob_bunkering_warning(self):
        """Warning (bukan blokir) kalau ROB FO/DO naik dari laporan sebelumnya tanpa
        event bunkering (call_purpose='bunkering' dengan ATB/ATD) tercatat."""
        self.ensure_one()
        previous = self.search([
            ('voyage_id', '=', self.voyage_id.id),
            ('state', '=', 'approved'),
            ('report_datetime', '<', self.report_datetime),
        ], order='report_datetime desc', limit=1)
        if not previous:
            return
        rob_increased = self.rob_fo > previous.rob_fo or self.rob_do > previous.rob_do
        if not rob_increased:
            return
        bunkering_calls = self.voyage_id.port_call_ids.filtered(
            lambda c: c.call_purpose == 'bunkering' and c.atb
            and previous.report_datetime <= c.atb <= self.report_datetime
        )
        if not bunkering_calls:
            self.voyage_id.message_post(body=_(
                '⚠️ Peringatan: ROB FO/DO naik pada noon report %s tanpa event bunkering '
                'tercatat di rentang waktu terkait.'
            ) % self.report_datetime)
