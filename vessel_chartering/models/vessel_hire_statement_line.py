# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class VesselHireStatementLine(models.Model):
    _name = 'vessel.hire.statement.line'
    _description = 'Hire Statement Line (Time Charter)'
    _order = 'period_start'

    contract_id = fields.Many2one(
        'vessel.charter.contract', string='Kontrak',
        required=True, ondelete='cascade', index=True,
        domain=[('contract_type', '=', 'time')],
    )
    period_start = fields.Date(string='Periode Mulai', required=True)
    period_end = fields.Date(string='Periode Selesai', required=True)
    days_in_period = fields.Float(
        string='Hari dalam Periode', compute='_compute_days_in_period', store=True,
    )
    offhire_hours = fields.Float(
        string='Off-hire (jam)', compute='_compute_offhire_hours', store=True,
        help='Agregasi off-hire event yang overlap dengan periode ini (proporsional jika overlap sebagian).',
    )
    net_hire_days = fields.Float(
        string='Net Hire Days', compute='_compute_net_hire_days', store=True,
    )
    currency_id = fields.Many2one(
        related='contract_id.currency_id', string='Currency', readonly=True,
    )
    hire_amount = fields.Monetary(
        string='Hire Amount', compute='_compute_amounts', store=True,
        currency_field='currency_id',
    )
    cve_amount = fields.Monetary(
        string='C/V/E Amount', compute='_compute_amounts', store=True,
        currency_field='currency_id',
        help='Pro-rata bulanan dari cve_rate kontrak (basis 30 hari).',
    )
    bunker_adjustment = fields.Monetary(
        string='Bunker Adjustment (BOD/BOR)', currency_field='currency_id',
        help='Penyesuaian bunker on delivery/redelivery — manual di fase MVP.',
    )
    total_amount = fields.Monetary(
        string='Total Amount', compute='_compute_amounts', store=True,
        currency_field='currency_id',
    )
    invoice_id = fields.Many2one(
        'account.move', string='Invoice', readonly=True, copy=False,
        help='Diisi Sprint 6 saat invoice digenerate.',
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('invoiced', 'Invoiced'), ('paid', 'Paid')],
        string='Status', default='draft', copy=False,
    )

    @api.depends('period_start', 'period_end')
    def _compute_days_in_period(self):
        for rec in self:
            if rec.period_start and rec.period_end:
                rec.days_in_period = (rec.period_end - rec.period_start).days
            else:
                rec.days_in_period = 0.0

    @api.depends('contract_id.offhire_ids', 'contract_id.offhire_ids.datetime_start',
                 'contract_id.offhire_ids.datetime_end', 'period_start', 'period_end')
    def _compute_offhire_hours(self):
        for rec in self:
            if not rec.period_start or not rec.period_end:
                rec.offhire_hours = 0.0
                continue
            period_start_dt = fields.Datetime.to_datetime(rec.period_start)
            period_end_dt = fields.Datetime.to_datetime(rec.period_end)
            total = 0.0
            for off in rec.contract_id.offhire_ids:
                if not off.datetime_start or not off.datetime_end:
                    continue
                overlap_start = max(off.datetime_start, period_start_dt)
                overlap_end = min(off.datetime_end, period_end_dt)
                if overlap_end > overlap_start:
                    total += (overlap_end - overlap_start).total_seconds() / 3600.0
            rec.offhire_hours = total

    @api.depends('days_in_period', 'offhire_hours')
    def _compute_net_hire_days(self):
        for rec in self:
            rec.net_hire_days = rec.days_in_period - (rec.offhire_hours / 24.0)

    @api.depends('net_hire_days', 'contract_id.hire_rate', 'contract_id.cve_rate',
                 'days_in_period', 'bunker_adjustment')
    def _compute_amounts(self):
        for rec in self:
            rec.hire_amount = rec.net_hire_days * rec.contract_id.hire_rate
            rec.cve_amount = (rec.contract_id.cve_rate or 0.0) * rec.days_in_period / 30.0
            rec.total_amount = rec.hire_amount + rec.cve_amount + (rec.bunker_adjustment or 0.0)

    @api.constrains('period_start', 'period_end')
    def _check_period(self):
        for rec in self:
            if rec.period_start and rec.period_end and rec.period_end <= rec.period_start:
                raise ValidationError(_('Periode selesai harus setelah periode mulai.'))

    @api.constrains('contract_id', 'period_start', 'period_end')
    def _check_no_duplicate_period(self):
        for rec in self:
            duplicate = self.search([
                ('contract_id', '=', rec.contract_id.id),
                ('period_start', '=', rec.period_start),
                ('id', '!=', rec.id),
            ])
            if duplicate:
                raise ValidationError(_(
                    'Kontrak %(contract)s sudah punya hire statement untuk periode mulai %(date)s.'
                ) % {'contract': rec.contract_id.name, 'date': rec.period_start})
