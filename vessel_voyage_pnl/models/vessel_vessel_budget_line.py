# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

MONTH = [(str(i), str(i)) for i in range(1, 13)]


class VesselVesselBudgetLine(models.Model):
    _name = 'vessel.vessel.budget.line'
    _description = 'Baris Budget Bulanan per Kategori Biaya'
    _order = 'budget_id, month'

    budget_id = fields.Many2one(
        'vessel.vessel.budget', string='Budget', required=True, ondelete='cascade',
    )
    month = fields.Selection(MONTH, string='Bulan', required=True)
    cost_category_id = fields.Many2one(
        'vessel.pnl.cost.category', string='Kategori Biaya', required=True,
    )
    planned_amount = fields.Monetary(string='Rencana')
    actual_amount = fields.Monetary(
        string='Realisasi', compute='_compute_actual_amount',
        help='On-the-fly dari vessel.voyage.pnl.line (kategori + bulan terkait), '
             'tidak store berat sesuai §4.4 tech spec.',
    )
    variance_amount = fields.Monetary(string='Variance', compute='_compute_variance')
    variance_pct = fields.Float(string='Variance (%)', compute='_compute_variance')
    currency_id = fields.Many2one(related='budget_id.currency_id', store=True, readonly=True)

    @api.depends('budget_id.vessel_id', 'budget_id.year', 'month', 'cost_category_id')
    def _compute_actual_amount(self):
        for line in self:
            vessel = line.budget_id.vessel_id
            if not (vessel and line.budget_id.year and line.month and line.cost_category_id):
                line.actual_amount = 0.0
                continue
            year, month = line.budget_id.year, int(line.month)
            first = fields.Date.to_date('%04d-%02d-01' % (year, month))
            next_first = (
                fields.Date.to_date('%04d-01-01' % (year + 1)) if month == 12
                else fields.Date.to_date('%04d-%02d-01' % (year, month + 1))
            )
            pnl_lines = self.env['vessel.voyage.pnl.line'].search([
                ('cost_category_id', '=', line.cost_category_id.id),
                ('pnl_id.vessel_id', '=', vessel.id),
                ('pnl_id.voyage_id.date_departure', '>=', first),
                ('pnl_id.voyage_id.date_departure', '<', next_first),
            ])
            line.actual_amount = sum(abs(a) for a in pnl_lines.mapped('amount'))

    @api.model
    def _calc_variance(self, planned_amount, actual_amount):
        """Pure function — gampang di-unit-test tanpa fixture DB (pola sama Sprint 17
        allocation methods). §10.8 acceptance criteria: planned 50,000, actual 65,000
        -> variance_pct 30%."""
        variance_amount = actual_amount - planned_amount
        variance_pct = (variance_amount / planned_amount) * 100.0 if planned_amount else 0.0
        return variance_amount, variance_pct

    @api.depends('planned_amount', 'actual_amount')
    def _compute_variance(self):
        for line in self:
            line.variance_amount, line.variance_pct = self._calc_variance(
                line.planned_amount, line.actual_amount,
            )

    def _check_variance_threshold(self):
        """§4.4 — threshold per-kapal (fleet.vehicle.budget_variance_threshold_pct),
        fallback default global res.company — pola identik _check_variance_threshold
        di vessel.port.disbursement (vessel_voyage_operations Sprint 12)."""
        self.ensure_one()
        vessel = self.budget_id.vessel_id
        threshold = vessel.budget_variance_threshold_pct \
            or self.budget_id.company_id.default_budget_variance_threshold_pct
        if not threshold or abs(self.variance_pct) <= threshold:
            return
        manager_group = self.env.ref('fleet.fleet_group_manager', raise_if_not_found=False)
        recipients = manager_group.user_ids if manager_group else self.env['res.users']
        existing_users = self.env['mail.activity'].search([
            ('res_model', '=', 'vessel.vessel.budget'),
            ('res_id', '=', self.budget_id.id),
        ]).mapped('user_id')
        new_recipients = recipients - existing_users
        for user in new_recipients:
            # Guard idempotency: -u ulang / re-trigger tidak boleh dobel activity
            # untuk budget + user yang sama.
            self.budget_id.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Budget Variance Tinggi: %s') % self.cost_category_id.name,
                note=_(
                    'Variance %(pct).1f%% (rencana %(planned).2f, realisasi %(actual).2f) '
                    'melebihi threshold %(threshold).1f%% untuk kapal %(vessel)s bulan %(month)s.'
                ) % {
                    'pct': self.variance_pct, 'planned': self.planned_amount,
                    'actual': self.actual_amount, 'threshold': threshold,
                    'vessel': vessel.name, 'month': self.month,
                },
                user_id=user.id,
            )
        if new_recipients:
            # §4.6 — email cuma dikirim sekali saat alert pertama kali muncul (dipakai
            # new_recipients yang sama sebagai guard idempotency dengan activity di atas).
            template = self.env.ref(
                'vessel_voyage_pnl.email_template_budget_variance_high', raise_if_not_found=False,
            )
            if template:
                template.send_mail(self.budget_id.id, force_send=False)
