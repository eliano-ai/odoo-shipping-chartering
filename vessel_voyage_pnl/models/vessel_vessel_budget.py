# -*- coding: utf-8 -*-
from datetime import date

from odoo import api, fields, models, _

STATE = [
    ('draft', 'Draft'),
    ('approved', 'Approved'),
]


class VesselVesselBudget(models.Model):
    _name = 'vessel.vessel.budget'
    _description = 'Budget Tahunan per Kapal'
    # mail.activity.mixin WAJIB (bukan cuma mail.thread seperti disebut sekilas di §3.5
    # tech spec) — cron _cron_budget_variance_alert manggil activity_schedule, tanpa
    # mixin ini akan AttributeError silent sampai cron pertama kali jalan (pelajaran
    # retro Sprint 8-14: pre-flight check mixin sebelum pakai activity_schedule).
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'year desc, vessel_id'

    vessel_id = fields.Many2one('fleet.vehicle', string='Kapal', required=True, tracking=True)
    year = fields.Integer(string='Tahun', required=True, tracking=True)
    budget_line_ids = fields.One2many(
        'vessel.vessel.budget.line', 'budget_id', string='Baris Budget',
    )
    total_budget_cost = fields.Monetary(
        string='Total Budget', compute='_compute_total_budget_cost', store=True,
    )
    total_actual_cost = fields.Monetary(
        string='Total Realisasi', compute='_compute_total_actual_cost', store=True,
        help='Dari vessel.vessel.pnl tahun berjalan (total_cost + idle_cost_allocated).',
    )
    state = fields.Selection(STATE, default='draft', required=True, tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string='Mata Uang',
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        'res.company', string='Perusahaan', required=True,
        default=lambda self: self.env.company,
    )

    _unique_vessel_year = models.Constraint(
        'UNIQUE(vessel_id, year)', 'Kapal ini sudah punya budget untuk tahun tersebut.',
    )

    @api.depends('budget_line_ids.planned_amount')
    def _compute_total_budget_cost(self):
        for rec in self:
            rec.total_budget_cost = sum(rec.budget_line_ids.mapped('planned_amount'))

    @api.depends('vessel_id', 'year')
    def _compute_total_actual_cost(self):
        for rec in self:
            if not rec.vessel_id or not rec.year:
                rec.total_actual_cost = 0.0
                continue
            vessel_pnls = self.env['vessel.vessel.pnl'].search([
                ('vessel_id', '=', rec.vessel_id.id),
                ('period_year', '=', rec.year),
            ])
            rec.total_actual_cost = sum(
                (p.total_cost + p.idle_cost_allocated) for p in vessel_pnls
            )

    def action_approve(self):
        for rec in self:
            rec.state = 'approved'

    def action_reset_draft(self):
        for rec in self:
            rec.state = 'draft'

    @api.model
    def _cron_budget_variance_alert(self):
        """§4.5 — bulanan, budget line dengan variance > threshold -> activity ke
        Fleet Manager. Hanya budget approved yang dicek (draft belum jadi acuan resmi)."""
        budgets = self.search([('state', '=', 'approved')])
        for budget in budgets:
            for line in budget.budget_line_ids:
                line._check_variance_threshold()

    @api.model
    def _demo_setup_budget(self):
        """§10.8 acceptance criteria — budget dengan variance di atas threshold default
        (20%). actual_amount kategori Maintenance bulan Juni 2026 untuk demo_vessel_barge_01
        real-computed = 30,000 (dari 2 voyage P&L Sprint 18) — planned sengaja diset 20,000
        supaya variance_pct = 50% (jauh di atas threshold), bukan replikasi literal
        angka 50,000/65,000 di teks tech spec (itu cuma contoh ilustratif, actual_amount
        di modul ini murni compute dari data riil, tidak bisa diinput manual)."""
        voyage3 = self.env.ref('vessel_voyage_operations.demo_voyage_3', raise_if_not_found=False)
        if not voyage3 or not voyage3.date_departure:
            return
        vessel = voyage3.vessel_id
        year = voyage3.date_departure.year

        budget = self.search([('vessel_id', '=', vessel.id), ('year', '=', year)], limit=1)
        if not budget:
            budget = self.create({'vessel_id': vessel.id, 'year': year})
            self.env['vessel.vessel.budget.line'].create({
                'budget_id': budget.id,
                'month': str(voyage3.date_departure.month),
                'cost_category_id': self.env.ref(
                    'vessel_voyage_pnl.cost_category_maintenance',
                ).id,
                'planned_amount': 20000,
            })
            budget.action_approve()
        self._cron_budget_variance_alert()
