# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class VesselVoyageEstimate(models.Model):
    _name = 'vessel.voyage.estimate'
    _description = 'Voyage Estimate (Pre-Fixture)'
    _order = 'contract_id, name'

    contract_id = fields.Many2one(
        'vessel.charter.contract', string='Kontrak',
        required=True, ondelete='cascade', index=True,
    )
    name = fields.Char(string='Revisi', required=True, copy=False)
    company_id = fields.Many2one(
        related='contract_id.company_id', store=True, readonly=True,
    )

    # ── Jarak & Kecepatan ─────────────────────────────────────────────────
    distance_nm = fields.Float(string='Jarak (NM)')
    speed_knots = fields.Float(string='Kecepatan (knots)')
    sea_days = fields.Float(
        string='Sea Days', compute='_compute_sea_days',
        store=True, readonly=False,
        help='Default = distance_nm / (speed_knots × 24). Bisa di-override manual.',
    )
    port_days_load = fields.Float(string='Port Days — Load')
    port_days_discharge = fields.Float(string='Port Days — Discharge')
    total_voyage_days = fields.Float(
        string='Total Voyage Days', compute='_compute_total_voyage_days', store=True,
    )

    # ── Bunker ────────────────────────────────────────────────────────────
    fo_consumption_sea = fields.Float(string='FO Consumption — Sea (MT/day)')
    fo_consumption_port = fields.Float(string='FO Consumption — Port (MT/day)')
    do_consumption_sea = fields.Float(string='DO Consumption — Sea (MT/day)')
    do_consumption_port = fields.Float(string='DO Consumption — Port (MT/day)')
    fo_price_usd = fields.Float(string='FO Price (USD/MT)')
    do_price_usd = fields.Float(string='DO Price (USD/MT)')
    usd_rate = fields.Float(
        string='Kurs USD→IDR', digits=(12, 4),
        default=lambda self: self._default_usd_rate(),
        help='Default dari res.currency.rate hari ini. Bisa di-override manual.',
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        related='contract_id.currency_id', readonly=True,
    )
    company_currency_id = fields.Many2one(
        'res.currency', string='Company Currency',
        default=lambda self: self.env.company.currency_id,
    )
    bunker_cost_usd = fields.Monetary(
        string='Bunker Cost (USD)', compute='_compute_bunker_cost',
        store=True, currency_field='currency_id',
    )
    bunker_cost_idr = fields.Monetary(
        string='Bunker Cost (IDR)', compute='_compute_bunker_cost',
        store=True, currency_field='company_currency_id',
    )

    # ── Cost Lain ─────────────────────────────────────────────────────────
    port_cost_estimate = fields.Monetary(string='Port Cost Estimate', currency_field='currency_id')
    other_cost_estimate = fields.Monetary(string='Other Cost Estimate', currency_field='currency_id')
    charter_in_cost = fields.Monetary(
        string='Charter-In Cost (Relet)', currency_field='currency_id',
    )

    # ── Hasil ─────────────────────────────────────────────────────────────
    revenue_estimate = fields.Monetary(
        string='Revenue Estimate', compute='_compute_result',
        store=True, currency_field='currency_id',
    )
    total_cost_estimate = fields.Monetary(
        string='Total Cost Estimate', compute='_compute_result',
        store=True, currency_field='currency_id',
    )
    voyage_result = fields.Monetary(
        string='Voyage Result', compute='_compute_result',
        store=True, currency_field='currency_id',
    )
    tce_per_day = fields.Monetary(
        string='TCE per Day', compute='_compute_result',
        store=True, currency_field='currency_id',
        help='Time Charter Equivalent — (Revenue - Voyage Cost) / Total Voyage Days.',
    )

    state = fields.Selection(
        [('draft', 'Draft'), ('selected', 'Selected (Baseline)')],
        string='Status', default='draft', required=True, copy=False,
    )

    # ─────────────────────────────────────────────────────────────────────
    # Defaults
    # ─────────────────────────────────────────────────────────────────────

    def _default_usd_rate(self):
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        company_currency = self.env.company.currency_id
        if not usd or not company_currency or usd == company_currency:
            return 0.0
        rate = self.env['res.currency.rate'].search([
            ('currency_id', '=', usd.id),
            ('name', '<=', fields.Date.today()),
            ('company_id', 'in', (self.env.company.id, False)),
        ], order='name desc', limit=1)
        if not rate or not rate.rate:
            return 0.0
        # res.currency.rate.rate = company_currency per 1 unit of foreign currency
        # (inverse companding tergantung setup); pakai representasi langsung.
        return 1 / rate.rate if rate.rate else 0.0

    # ─────────────────────────────────────────────────────────────────────
    # Compute
    # ─────────────────────────────────────────────────────────────────────

    @api.depends('distance_nm', 'speed_knots')
    def _compute_sea_days(self):
        for rec in self:
            if rec.speed_knots:
                rec.sea_days = rec.distance_nm / (rec.speed_knots * 24)
            else:
                rec.sea_days = 0.0

    @api.depends('sea_days', 'port_days_load', 'port_days_discharge')
    def _compute_total_voyage_days(self):
        for rec in self:
            rec.total_voyage_days = rec.sea_days + rec.port_days_load + rec.port_days_discharge

    @api.depends(
        'fo_consumption_sea', 'fo_consumption_port', 'do_consumption_sea', 'do_consumption_port',
        'fo_price_usd', 'do_price_usd', 'sea_days', 'port_days_load', 'port_days_discharge',
        'usd_rate',
    )
    def _compute_bunker_cost(self):
        for rec in self:
            port_days = rec.port_days_load + rec.port_days_discharge
            fo_qty = rec.fo_consumption_sea * rec.sea_days + rec.fo_consumption_port * port_days
            do_qty = rec.do_consumption_sea * rec.sea_days + rec.do_consumption_port * port_days
            cost_usd = fo_qty * rec.fo_price_usd + do_qty * rec.do_price_usd
            rec.bunker_cost_usd = cost_usd
            rec.bunker_cost_idr = cost_usd * rec.usd_rate

    @api.depends(
        'contract_id.freight_amount_estimate', 'bunker_cost_usd', 'port_cost_estimate',
        'other_cost_estimate', 'charter_in_cost', 'total_voyage_days',
    )
    def _compute_result(self):
        for rec in self:
            rec.revenue_estimate = rec.contract_id.freight_amount_estimate
            rec.total_cost_estimate = (
                rec.bunker_cost_usd + rec.port_cost_estimate
                + rec.other_cost_estimate + rec.charter_in_cost
            )
            rec.voyage_result = rec.revenue_estimate - rec.total_cost_estimate
            if rec.total_voyage_days:
                rec.tce_per_day = rec.voyage_result / rec.total_voyage_days
            else:
                rec.tce_per_day = 0.0

    # ─────────────────────────────────────────────────────────────────────
    # Constraints
    # ─────────────────────────────────────────────────────────────────────

    @api.constrains('state', 'contract_id')
    def _check_single_selected(self):
        for rec in self:
            if rec.state != 'selected':
                continue
            others = self.search([
                ('contract_id', '=', rec.contract_id.id),
                ('state', '=', 'selected'),
                ('id', '!=', rec.id),
            ])
            if others:
                raise ValidationError(_(
                    'Kontrak %(contract)s sudah punya estimate lain (%(other)s) '
                    'yang berstatus Selected. Batalkan pilihan itu dulu.'
                ) % {'contract': rec.contract_id.name, 'other': others[0].name})

    # ─────────────────────────────────────────────────────────────────────
    # ORM
    # ─────────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') and vals.get('contract_id'):
                count = self.search_count([('contract_id', '=', vals['contract_id'])])
                vals['name'] = 'EST-%03d' % (count + 1)
        return super().create(vals_list)

    # ─────────────────────────────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────────────────────────────

    def action_select_baseline(self):
        for rec in self:
            rec.contract_id.estimate_ids.filtered(
                lambda e: e.id != rec.id
            ).write({'state': 'draft'})
            rec.state = 'selected'
