# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

EVENT_TYPE = [
    ('delivery', 'Delivery'),
    ('redelivery', 'Redelivery'),
]

PRICE_SOURCE = [
    ('last_purchase', 'Last Purchase'),
    ('market_reference', 'Market Reference'),
    ('manual', 'Manual'),
]

SETTLEMENT_DIRECTION = [
    ('delivery', 'Charterer bayar Owner'),
    ('redelivery', 'Owner bayar Charterer'),
]

STATE = [
    ('draft', 'Draft'),
    ('confirmed', 'Confirmed'),
    ('settled', 'Settled'),
]


class VesselBunkerBodBor(models.Model):
    _name = 'vessel.bunker.bod.bor'
    _description = 'BOD/BOR — Bunker on Delivery/Redelivery (Time Charter)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'event_date desc'

    contract_id = fields.Many2one(
        'vessel.charter.contract', string='Kontrak Time Charter', required=True,
        domain=[('contract_type', '=', 'time')],
    )
    event_type = fields.Selection(EVENT_TYPE, required=True)
    event_date = fields.Datetime(string='Tanggal Event', compute='_compute_event_date', store=True)
    rob_fo = fields.Float(string='ROB FO (MT)')
    rob_do = fields.Float(string='ROB DO (MT)')
    price_source = fields.Selection(PRICE_SOURCE, default='last_purchase', required=True)
    price_fo_usd_mt = fields.Float(string='Harga FO (USD/MT)')
    price_do_usd_mt = fields.Float(string='Harga DO (USD/MT)')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.ref('base.USD', raise_if_not_found=False),
    )
    settlement_amount = fields.Monetary(
        string='Settlement Amount', compute='_compute_settlement_amount', store=True,
    )
    settlement_direction = fields.Selection(
        SETTLEMENT_DIRECTION, compute='_compute_settlement_direction', store=True,
    )
    hire_statement_line_id = fields.Many2one(
        'vessel.hire.statement.line', string='Hire Statement Line',
    )
    state = fields.Selection(STATE, default='draft', required=True, tracking=True, copy=False)
    company_id = fields.Many2one(
        'res.company', string='Perusahaan', required=True,
        default=lambda self: self.env.company,
    )

    _unique_contract_event = models.Constraint(
        'UNIQUE(contract_id, event_type)',
        'Kontrak ini sudah punya BOD/BOR untuk event yang sama.',
    )

    @api.depends('contract_id.name', 'event_type')
    def _compute_display_name(self):
        labels = dict(EVENT_TYPE)
        for rec in self:
            rec.display_name = _('%(contract)s — %(event)s') % {
                'contract': rec.contract_id.name or _('Kontrak'),
                'event': labels.get(rec.event_type, rec.event_type or ''),
            }

    @api.depends('contract_id.delivery_date', 'contract_id.redelivery_date', 'event_type')
    def _compute_event_date(self):
        for rec in self:
            rec.event_date = (
                rec.contract_id.delivery_date if rec.event_type == 'delivery'
                else rec.contract_id.redelivery_date
            )

    @api.depends('rob_fo', 'rob_do', 'price_fo_usd_mt', 'price_do_usd_mt')
    def _compute_settlement_amount(self):
        for rec in self:
            rec.settlement_amount = (
                rec.rob_fo * rec.price_fo_usd_mt + rec.rob_do * rec.price_do_usd_mt
            )

    @api.depends('event_type')
    def _compute_settlement_direction(self):
        for rec in self:
            rec.settlement_direction = rec.event_type

    def _get_nearest_noon_report_rob(self):
        """Cari noon report terdekat dengan event_date milik voyage kontrak ini."""
        self.ensure_one()
        if not self.event_date:
            return 0.0, 0.0
        voyages = self.env['vessel.voyage'].search([
            ('charter_contract_id', '=', self.contract_id.id),
        ])
        reports = self.env['vessel.noon.report'].search([
            ('voyage_id', 'in', voyages.ids), ('state', '=', 'approved'),
        ], order='report_datetime desc')
        if not reports:
            return 0.0, 0.0
        nearest = min(reports, key=lambda r: abs((r.report_datetime - self.event_date).total_seconds()))
        return nearest.rob_fo, nearest.rob_do

    def _get_price_for_source(self):
        self.ensure_one()
        if self.price_source == 'manual':
            return self.price_fo_usd_mt, self.price_do_usd_mt
        if self.price_source == 'last_purchase':
            deliveries = self.env['vessel.bunker.delivery'].search([
                ('vessel_id', '=', self.contract_id.vessel_id.id),
                ('state', '=', 'confirmed'),
                ('delivery_datetime', '<=', self.event_date),
            ], order='delivery_datetime desc')
            fo_delivery = deliveries.filtered(lambda d: d.fuel_type_id.code == 'MFO')[:1]
            do_delivery = deliveries.filtered(lambda d: d.fuel_type_id.code in ('HSD', 'MGO'))[:1]
            fo_price = (
                fo_delivery.account_move_id.invoice_line_ids[:1].price_unit if fo_delivery else 0.0
            )
            do_price = (
                do_delivery.account_move_id.invoice_line_ids[:1].price_unit if do_delivery else 0.0
            )
            return fo_price, do_price
        if self.price_source == 'market_reference':
            date_ref = self.event_date.date() if self.event_date else fields.Date.context_today(self)
            fo_ref = self.env['vessel.bunker.price.reference'].search([
                ('fuel_type_id.code', '=', 'MFO'), ('date', '<=', date_ref),
            ], order='date desc', limit=1)
            do_ref = self.env['vessel.bunker.price.reference'].search([
                ('fuel_type_id.code', 'in', ('HSD', 'MGO')), ('date', '<=', date_ref),
            ], order='date desc', limit=1)
            return (fo_ref.price_usd_mt if fo_ref else 0.0), (do_ref.price_usd_mt if do_ref else 0.0)
        return 0.0, 0.0

    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Hanya BOD/BOR Draft yang bisa dikonfirmasi.'))
            if not rec.rob_fo and not rec.rob_do:
                rec.rob_fo, rec.rob_do = rec._get_nearest_noon_report_rob()
            if rec.price_source != 'manual':
                rec.price_fo_usd_mt, rec.price_do_usd_mt = rec._get_price_for_source()
            rec.state = 'confirmed'
            rec._send_ready_to_settle_email()

    def _send_ready_to_settle_email(self):
        self.ensure_one()
        template = self.env.ref(
            'vessel_bunker_management.email_template_bunker_bod_bor_ready_to_settle',
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.id, force_send=False)

    def action_settle(self):
        """§4.4 — group_bunker_manager only (approval eksplisit sebelum masuk hire
        statement final, §8 keputusan desain)."""
        if not self.env.user.has_group('vessel_bunker_management.group_bunker_manager'):
            raise UserError(_('Hanya Bunker Manager yang bisa settle BOD/BOR.'))
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(_('Hanya BOD/BOR Confirmed yang bisa di-settle.'))
            if not rec.hire_statement_line_id:
                raise UserError(_('Pilih Hire Statement Line target sebelum settle.'))
            amount = (
                rec.settlement_amount if rec.settlement_direction == 'delivery'
                else -rec.settlement_amount
            )
            rec.hire_statement_line_id.bunker_adjustment = amount
            rec.state = 'settled'

    @api.model
    def _demo_setup_bod_bor_scenario(self):
        """§10.6/§10.7 acceptance criteria — kontrak time charter dengan delivery_date
        ter-set (demo_contract_time_out_1, sudah ada sejak vessel_chartering) -> draft
        BOD/BOR, confirm (ROB dari noon report terdekat, harga dari sumber terpilih),
        settle -> bunker_adjustment di hire statement line terisi benar (+/-).

        NB: demo_contract_time_out_1.delivery_date sudah ter-set sejak CREATE awal
        (bukan lewat write() belakangan), jadi hook otomatis di vessel.charter.contract
        tidak sempat kepanggil untuk record demo ini — dibuat manual di sini. Hook-nya
        sendiri (trigger dari write()) diuji terpisah via unit test dengan kontrak baru."""
        contract = self.env.ref('vessel_chartering.demo_contract_time_out_1', raise_if_not_found=False)
        if not contract or not contract.delivery_date:
            return
        bod = self.search([('contract_id', '=', contract.id), ('event_type', '=', 'delivery')], limit=1)
        if not bod:
            # price_source='market_reference' (bukan default 'last_purchase') —
            # demo_contract_time_out_1 pakai demo_vessel_mv_01, kapal yang belum
            # pernah punya bunker delivery di demo manapun, jadi 'last_purchase'
            # akan selalu 0. Price reference tersedia untuk semua kapal.
            bod = self.create({
                'contract_id': contract.id, 'event_type': 'delivery',
                'price_source': 'market_reference',
            })
        if bod.state == 'draft':
            bod.action_confirm()
        if bod.state == 'confirmed':
            line = self.env['vessel.hire.statement.line'].search([
                ('contract_id', '=', contract.id),
            ], limit=1)
            if not line:
                line = self.env['vessel.hire.statement.line'].create({
                    'contract_id': contract.id,
                    'period_start': contract.delivery_date.date(),
                    'period_end': contract.delivery_date.date() + timedelta(days=15),
                })
            bod.hire_statement_line_id = line.id
            # Set field langsung (bukan action_settle()) — method itu guard
            # has_group('group_bunker_manager'), user yang jalanin instalasi module
            # belum tentu member grup itu (pola sama Sprint 24/vessel_voyage_pnl
            # Sprint 17: __system__ != base.user_admin).
            amount = (
                bod.settlement_amount if bod.settlement_direction == 'delivery'
                else -bod.settlement_amount
            )
            bod.hire_statement_line_id.bunker_adjustment = amount
            bod.state = 'settled'
