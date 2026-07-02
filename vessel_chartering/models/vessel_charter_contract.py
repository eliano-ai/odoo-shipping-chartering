# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


CONTRACT_TYPE = [
    ('voyage', 'Voyage Charter'),
    ('time', 'Time Charter'),
    ('coa', 'Contract of Affreightment (COA)'),
]

DIRECTION = [
    ('out', 'Charter Out (Revenue)'),
    ('in', 'Charter In (Cost)'),
]

EXCHANGE_RATE_POLICY = [
    ('system', 'Kurs Sistem (tanggal invoice)'),
    ('fixed', 'Kurs Tetap (manual)'),
]

FREIGHT_BASIS = [
    ('per_mt', 'Per MT'),
    ('lumpsum', 'Lumpsum'),
]

HIRE_PAYMENT_TERM = [
    ('15_days_advance', '15 Hari di Muka'),
    ('monthly_advance', 'Bulanan di Muka'),
    ('monthly_arrears', 'Bulanan di Belakang'),
]

STATE = [
    ('draft', 'Draft'),
    ('negotiation', 'Negotiation'),
    ('confirmed', 'Confirmed'),
    ('in_progress', 'In Progress'),
    ('completed', 'Completed'),
    ('closed', 'Closed'),
    ('cancelled', 'Cancelled'),
]


class VesselCharterContract(models.Model):
    _name = 'vessel.charter.contract'
    _description = 'Charter Party — Voyage/Time Charter & COA'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'

    # ── Field Umum ────────────────────────────────────────────────────────
    name = fields.Char(
        string='Nomor Kontrak', readonly=True, copy=False,
        default=lambda self: _('New'),
    )
    contract_type = fields.Selection(
        CONTRACT_TYPE, string='Tipe Kontrak',
        required=True, default='voyage', tracking=True,
    )
    direction = fields.Selection(
        DIRECTION, string='Arah',
        required=True, default='out', tracking=True,
        help='Charter Out: perusahaan menyewakan kapal (revenue). '
             'Charter In: perusahaan menyewa kapal pihak ketiga (cost).',
    )
    partner_id = fields.Many2one(
        'res.partner', string='Charterer / Owner',
        required=True, tracking=True,
        help='Charterer jika direction=out, Owner kapal jika direction=in.',
    )
    broker_id = fields.Many2one('res.partner', string='Broker')
    brokerage_pct = fields.Float(string='Komisi Broker (%)')
    vessel_id = fields.Many2one(
        'fleet.vehicle', string='Kapal',
        domain=[('is_vessel', '=', True)], tracking=True,
        help='Tidak wajib untuk COA — nominasi kapal dilakukan per shipment (child voyage).',
    )
    tug_id = fields.Many2one(
        'fleet.vehicle', string='Kapal Tunda (Tug)',
        domain=[('is_vessel', '=', True)],
        help='Pairing tug untuk barge, jika berlaku.',
    )
    cargo_type_id = fields.Many2one('vessel.cargo.type', string='Tipe Kargo')
    cargo_qty = fields.Float(string='Qty Kargo (MT)')
    qty_tolerance_pct = fields.Float(
        string='Toleransi Qty (%)',
        help='MOLOO/MOLCO — toleransi ± dari cargo_qty.',
    )
    date_start = fields.Date(
        string='Tanggal Mulai (Laycan / Periode)', tracking=True,
    )
    date_end = fields.Date(
        string='Tanggal Selesai (Cancelling / Periode)', tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency', string='Mata Uang Kontrak',
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False),
    )
    invoice_currency_id = fields.Many2one(
        'res.currency', string='Mata Uang Invoice',
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False),
    )
    exchange_rate_policy = fields.Selection(
        EXCHANGE_RATE_POLICY, string='Kebijakan Kurs',
        default='system', required=True,
    )
    fixed_exchange_rate = fields.Float(
        string='Kurs Tetap', digits=(12, 4),
        help='Terisi jika Kebijakan Kurs = Kurs Tetap.',
    )
    charter_terms_id = fields.Many2one('vessel.charter.terms', string='Charter Terms')
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account (Voyage)',
        readonly=True, copy=False,
    )
    company_id = fields.Many2one(
        'res.company', string='Perusahaan', required=True,
        default=lambda self: self.env.company,
    )
    user_id = fields.Many2one(
        'res.users', string='Chartering Manager',
        default=lambda self: self.env.user,
    )
    state = fields.Selection(
        STATE, string='Status',
        default='draft', required=True, tracking=True, copy=False, index=True,
    )

    # ── Field Voyage Charter ──────────────────────────────────────────────
    freight_rate = fields.Monetary(string='Freight Rate (USD/MT)', currency_field='currency_id')
    freight_basis = fields.Selection(FREIGHT_BASIS, string='Basis Freight', default='per_mt')
    lumpsum_amount = fields.Monetary(string='Lumpsum Amount', currency_field='currency_id')
    load_port_id = fields.Many2one(
        'res.partner', string='Load Port', domain=[('is_port', '=', True)],
    )
    discharge_port_id = fields.Many2one(
        'res.partner', string='Discharge Port', domain=[('is_port', '=', True)],
    )
    laytime_allowed_load = fields.Float(string='Laytime Allowed — Load (jam)')
    laytime_allowed_discharge = fields.Float(string='Laytime Allowed — Discharge (jam)')
    laytime_reversible = fields.Boolean(string='Laytime Reversible')
    turn_time_hours = fields.Float(string='Turn Time (jam)')
    demurrage_rate = fields.Monetary(string='Demurrage Rate (USD/day)', currency_field='currency_id')
    despatch_rate = fields.Monetary(string='Despatch Rate (USD/day)', currency_field='currency_id')
    bl_date = fields.Date(string='Tanggal Bill of Lading')
    bl_qty = fields.Float(string='Qty B/L (MT)')

    # ── Field Time Charter ────────────────────────────────────────────────
    hire_rate = fields.Monetary(string='Hire Rate (USD/day)', currency_field='currency_id')
    hire_payment_term = fields.Selection(HIRE_PAYMENT_TERM, string='Payment Term')
    delivery_date = fields.Datetime(string='Delivery (On-hire)')
    redelivery_date = fields.Datetime(string='Redelivery (Off-hire)')
    delivery_place = fields.Many2one(
        'res.partner', string='Delivery Place', domain=[('is_port', '=', True)],
    )
    redelivery_place = fields.Many2one(
        'res.partner', string='Redelivery Place', domain=[('is_port', '=', True)],
    )
    cve_rate = fields.Monetary(string='C/V/E Rate (USD/bulan)', currency_field='currency_id')
    total_offhire_hours = fields.Float(
        string='Total Off-hire (jam)', compute='_compute_total_offhire_hours', store=True,
    )

    # ── Field COA ─────────────────────────────────────────────────────────
    coa_id = fields.Many2one(
        'vessel.charter.contract', string='Parent COA',
        domain=[('contract_type', '=', 'coa')],
        help='Diisi jika kontrak ini adalah shipment/nominasi dari sebuah COA.',
    )
    total_qty_commitment = fields.Float(string='Total Komitmen Qty (MT)')
    shipment_ids = fields.One2many(
        'vessel.charter.contract', 'coa_id', string='Shipment / Nominasi',
    )
    qty_shipped = fields.Float(
        string='Qty Sudah Dikirim (MT)', compute='_compute_coa_qty', store=True,
    )
    qty_remaining = fields.Float(
        string='Qty Tersisa (MT)', compute='_compute_coa_qty', store=True,
    )

    # ── Relet ─────────────────────────────────────────────────────────────
    relet_source_id = fields.Many2one(
        'vessel.charter.contract', string='Sumber Relet',
        domain=[('direction', '=', 'in')],
        help='Jika kontrak charter-out ini adalah relet dari kontrak charter-in tertentu.',
    )

    # ── Field Compute / Monitoring ────────────────────────────────────────
    freight_amount_estimate = fields.Monetary(
        string='Estimasi Freight', compute='_compute_freight_amounts',
        currency_field='currency_id', store=True,
    )
    freight_amount_final = fields.Monetary(
        string='Freight Final (B/L)', compute='_compute_freight_amounts',
        currency_field='currency_id', store=True,
    )
    demurrage_amount_total = fields.Monetary(
        string='Total Demurrage', currency_field='currency_id',
        default=0.0, copy=False,
        help='Diagregasi dari laytime approved — diisi Sprint 4.',
    )
    despatch_amount_total = fields.Monetary(
        string='Total Despatch', currency_field='currency_id',
        default=0.0, copy=False,
        help='Diagregasi dari laytime approved — diisi Sprint 4.',
    )
    invoiced_amount = fields.Monetary(
        string='Sudah Diinvoice', currency_field='currency_id',
        default=0.0, copy=False,
        help='Diisi Sprint 6.',
    )
    residual_amount = fields.Monetary(
        string='Sisa Belum Diinvoice', currency_field='currency_id',
        default=0.0, copy=False,
        help='Diisi Sprint 6.',
    )
    estimate_count = fields.Integer(string='Jumlah Estimate', compute='_compute_smart_button_counts')
    laytime_count = fields.Integer(string='Jumlah Laytime', compute='_compute_smart_button_counts')
    invoice_count = fields.Integer(string='Jumlah Invoice', compute='_compute_smart_button_counts')

    note = fields.Text(string='Catatan')

    # ─────────────────────────────────────────────────────────────────────
    # Compute
    # ─────────────────────────────────────────────────────────────────────

    @api.depends('freight_rate', 'cargo_qty', 'freight_basis', 'lumpsum_amount', 'bl_qty')
    def _compute_freight_amounts(self):
        for rec in self:
            if rec.freight_basis == 'lumpsum':
                rec.freight_amount_estimate = rec.lumpsum_amount
                rec.freight_amount_final = rec.lumpsum_amount
            else:
                rec.freight_amount_estimate = rec.freight_rate * rec.cargo_qty
                rec.freight_amount_final = rec.freight_rate * rec.bl_qty if rec.bl_qty else 0.0

    @api.depends('shipment_ids', 'shipment_ids.state', 'shipment_ids.bl_qty', 'total_qty_commitment')
    def _compute_coa_qty(self):
        for rec in self:
            shipped = rec.shipment_ids.filtered(
                lambda s: s.state in ('completed', 'closed')
            )
            rec.qty_shipped = sum(shipped.mapped('bl_qty'))
            rec.qty_remaining = rec.total_qty_commitment - rec.qty_shipped

    def _compute_total_offhire_hours(self):
        # offhire_ids belum ada (Sprint 5) — return 0 sementara, TODO Sprint 5
        for rec in self:
            rec.total_offhire_hours = 0.0

    def _compute_smart_button_counts(self):
        # estimate_ids/laytime_ids/invoice_ids belum ada — TODO Sprint 3/4/6
        for rec in self:
            rec.estimate_count = 0
            rec.laytime_count = 0
            rec.invoice_count = 0

    # ─────────────────────────────────────────────────────────────────────
    # Constraints
    # ─────────────────────────────────────────────────────────────────────

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_(
                    'Tanggal selesai tidak boleh sebelum tanggal mulai.'
                ))

    @api.constrains('contract_type', 'shipment_ids')
    def _check_coa_no_direct_laytime(self):
        for rec in self:
            if rec.contract_type == 'coa' and rec.vessel_id:
                raise ValidationError(_(
                    'COA tidak boleh punya kapal langsung — nominasi kapal '
                    'dilakukan per shipment (child voyage charter).'
                ))

    def _check_vessel_overlap(self):
        """Warning (bukan blokir) jika kapal punya kontrak lain yang overlap,
        kecuali overlap penuh dengan kontrak yang sudah in_progress."""
        for rec in self:
            if not rec.vessel_id or not rec.date_start:
                continue
            domain = [
                ('vessel_id', '=', rec.vessel_id.id),
                ('id', '!=', rec.id),
                ('state', 'in', ('confirmed', 'in_progress')),
            ]
            others = self.search(domain)
            for other in others:
                if not other.date_start:
                    continue
                end_a = rec.date_end or rec.date_start
                end_b = other.date_end or other.date_start
                overlap = rec.date_start <= end_b and other.date_start <= end_a
                if not overlap:
                    continue
                full_overlap_in_progress = (
                    other.state == 'in_progress'
                    and rec.date_start >= other.date_start
                    and end_a <= end_b
                )
                if full_overlap_in_progress:
                    raise ValidationError(_(
                        'Kapal %(vessel)s sudah punya kontrak In Progress (%(other)s) '
                        'yang overlap penuh dengan periode kontrak ini.'
                    ) % {'vessel': rec.vessel_id.name, 'other': other.name})
                rec.message_post(body=_(
                    '⚠️ Peringatan: periode kontrak ini beririsan dengan kontrak '
                    '%(other)s (%(state)s) untuk kapal yang sama.'
                ) % {'other': other.name, 'state': dict(STATE).get(other.state)})

    # ─────────────────────────────────────────────────────────────────────
    # ORM overrides
    # ─────────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                direction = vals.get('direction', 'out')
                seq_code = 'vessel.charter.contract.out' if direction == 'out' \
                    else 'vessel.charter.contract.in'
                vals['name'] = self.env['ir.sequence'].next_by_code(seq_code) or _('New')
        return super().create(vals_list)

    # ─────────────────────────────────────────────────────────────────────
    # State machine
    # ─────────────────────────────────────────────────────────────────────

    def action_send_negotiation(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Hanya kontrak Draft yang bisa dikirim untuk negosiasi.'))
            rec.state = 'negotiation'

    def action_confirm(self):
        for rec in self:
            if rec.state not in ('draft', 'negotiation'):
                raise UserError(_('Hanya kontrak Draft/Negotiation yang bisa dikonfirmasi.'))
            if rec.contract_type != 'coa':
                if not rec.vessel_id:
                    raise ValidationError(_('Kapal wajib diisi sebelum konfirmasi.'))
                if not rec.partner_id:
                    raise ValidationError(_('Charterer/Owner wajib diisi sebelum konfirmasi.'))
                if not rec.date_start:
                    raise ValidationError(_('Laycan/tanggal mulai wajib diisi sebelum konfirmasi.'))
                if rec.contract_type == 'voyage' and rec.freight_rate <= 0 and rec.freight_basis == 'per_mt':
                    raise ValidationError(_('Freight rate harus lebih besar dari 0.'))
                if rec.contract_type == 'time' and rec.hire_rate <= 0:
                    raise ValidationError(_('Hire rate harus lebih besar dari 0.'))
            rec._check_vessel_overlap()
            rec._ensure_voyage_analytic_account()
            rec.state = 'confirmed'
            rec.message_post(body=_('Fixture dikonfirmasi.'))

    def action_start(self):
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(_('Hanya kontrak Confirmed yang bisa dimulai.'))
            if rec.contract_type == 'time' and not rec.delivery_date:
                rec.delivery_date = fields.Datetime.now()
            rec.state = 'in_progress'
            rec.message_post(body=_('Kontrak dimulai (in progress).'))

    def action_complete(self):
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError(_('Hanya kontrak In Progress yang bisa diselesaikan.'))
            if rec.contract_type == 'voyage' and not rec.bl_qty:
                raise ValidationError(_(
                    'Qty B/L wajib diisi sebelum kontrak voyage diselesaikan.'
                ))
            if rec.contract_type == 'time' and not rec.redelivery_date:
                rec.redelivery_date = fields.Datetime.now()
            rec.state = 'completed'
            rec.message_post(body=_('Kontrak selesai (completed).'))

    def action_close(self):
        for rec in self:
            if rec.state != 'completed':
                raise UserError(_('Hanya kontrak Completed yang bisa ditutup.'))
            rec.state = 'closed'
            rec.message_post(body=_('Kontrak ditutup.'))

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'in_progress':
            raise UserError(_(
                'Tidak bisa membatalkan kontrak yang sedang In Progress.'
            ))
        if self.state in ('completed', 'closed'):
            raise UserError(_(
                'Kontrak yang sudah Completed/Closed tidak bisa dibatalkan.'
            ))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Batalkan Kontrak'),
            'res_model': 'vessel.charter.cancel.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_contract_id': self.id},
        }

    def action_reset_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_('Hanya kontrak Cancelled yang bisa dikembalikan ke Draft.'))
            rec.state = 'draft'

    def _ensure_voyage_analytic_account(self):
        plan = self.env.ref(
            'vessel_chartering.account_analytic_plan_voyage', raise_if_not_found=False,
        )
        if not plan:
            return
        for rec in self:
            if rec.analytic_account_id:
                continue
            account = self.env['account.analytic.account'].create({
                'name': rec.name,
                'plan_id': plan.id,
                'company_id': rec.company_id.id,
            })
            rec.analytic_account_id = account

    # ─────────────────────────────────────────────────────────────────────
    # Smart button actions — placeholder, diisi Sprint 3/4/6
    # ─────────────────────────────────────────────────────────────────────

    def action_view_estimates(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Voyage Estimates — %s') % self.name,
            'res_model': 'vessel.voyage.estimate',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }

    def action_view_laytime(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Laytime — %s') % self.name,
            'res_model': 'vessel.laytime.calculation',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices — %s') % self.name,
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', [])],
        }
