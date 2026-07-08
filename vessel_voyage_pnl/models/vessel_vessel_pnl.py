# -*- coding: utf-8 -*-
from datetime import date

from odoo import api, fields, models, _

MONTH = [(str(i), str(i)) for i in range(1, 13)]

STATE = [
    ('draft', 'Draft'),
    ('closed', 'Closed'),
]


class VesselVesselPnl(models.Model):
    _name = 'vessel.vessel.pnl'
    _description = 'P&L Bulanan per Kapal'
    _order = 'period_year desc, period_month desc'

    vessel_id = fields.Many2one('fleet.vehicle', string='Kapal', required=True)
    period_month = fields.Selection(MONTH, string='Bulan', required=True)
    period_year = fields.Integer(string='Tahun', required=True)

    voyage_pnl_ids = fields.Many2many(
        'vessel.voyage.pnl', string='Voyage P&L Terkait',
        compute='_compute_voyage_pnl_ids',
    )

    total_revenue = fields.Monetary(
        string='Total Revenue', compute='_compute_totals', store=True,
    )
    total_cost = fields.Monetary(
        string='Total Cost', compute='_compute_totals', store=True,
        help='Direct cost + allocated cost, pro-rata sesuai hari overlap voyage di bulan ini.',
    )
    idle_cost_allocated = fields.Monetary(
        string='Idle Cost', compute='_compute_totals', store=True,
        help='Pool Maintenance bulanan kapal ini dikurangi yang sudah terserap voyage — '
             'MVP hanya hitung dari kategori Maintenance (satu-satunya yang punya sumber '
             'pool otomatis; Crew Cost/Depreciation selalu manual di MVP, tidak ada pool '
             'terukur untuk dihitung idle-nya).',
    )
    net_result = fields.Monetary(
        string='Net Result', compute='_compute_totals', store=True,
    )
    calendar_days = fields.Integer(string='Hari Kalender', compute='_compute_totals', store=True)
    voyage_days_total = fields.Float(
        string='Total Hari Voyage', compute='_compute_totals', store=True,
    )
    utilization_pct = fields.Float(
        string='Utilisasi (%)', compute='_compute_totals', store=True,
    )
    avg_tce = fields.Monetary(string='TCE Rata-rata', compute='_compute_totals', store=True)

    state = fields.Selection(STATE, default='draft', required=True)
    currency_id = fields.Many2one(
        'res.currency', string='Mata Uang',
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        'res.company', string='Perusahaan', required=True,
        default=lambda self: self.env.company,
    )

    _unique_vessel_period = models.Constraint(
        'UNIQUE(vessel_id, period_month, period_year)',
        'Kapal ini sudah punya P&L bulanan untuk periode tersebut.',
    )

    def _get_period_bounds(self):
        self.ensure_one()
        year, month = int(self.period_year), int(self.period_month)
        first = date(year, month, 1)
        next_first = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        return first, next_first

    def _get_overlapping_voyage_pnls(self):
        self.ensure_one()
        first, next_first = self._get_period_bounds()
        return self.env['vessel.voyage.pnl'].search([
            ('vessel_id', '=', self.vessel_id.id),
            ('voyage_id.date_departure', '<', next_first),
            ('voyage_id.date_arrival_final', '>=', first),
        ])

    @api.depends('vessel_id.name', 'period_month', 'period_year')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('%(vessel)s — P&L %(month)s/%(year)s') % {
                'vessel': rec.vessel_id.name or _('Kapal'),
                'month': rec.period_month or '',
                'year': rec.period_year or '',
            }

    @api.depends('vessel_id', 'period_month', 'period_year')
    def _compute_voyage_pnl_ids(self):
        for rec in self:
            rec.voyage_pnl_ids = rec._get_overlapping_voyage_pnls() if rec.vessel_id else False

    @api.depends('vessel_id', 'period_month', 'period_year')
    def _compute_totals(self):
        VoyagePnl = self.env['vessel.voyage.pnl']
        for rec in self:
            if not rec.vessel_id or not rec.period_month or not rec.period_year:
                rec.total_revenue = rec.total_cost = rec.idle_cost_allocated = 0.0
                rec.net_result = rec.calendar_days = rec.voyage_days_total = 0
                rec.utilization_pct = rec.avg_tce = 0.0
                continue

            first, next_first = rec._get_period_bounds()
            pnls = rec._get_overlapping_voyage_pnls()

            total_revenue = 0.0
            total_cost = 0.0
            voyage_days_total = 0.0
            tce_weighted_sum = 0.0
            maintenance_allocated_this_period = 0.0

            for pnl in pnls:
                voyage = pnl.voyage_id
                overlap_start = max(voyage.date_departure.date(), first)
                overlap_end = min(voyage.date_arrival_final.date(), next_first)
                overlap_days = max((overlap_end - overlap_start).days, 0)
                ratio = (overlap_days / pnl.voyage_days) if pnl.voyage_days else 0.0

                total_revenue += pnl.total_revenue * ratio
                total_cost += (pnl.total_direct_cost + pnl.total_allocated_cost) * ratio
                voyage_days_total += overlap_days
                tce_weighted_sum += pnl.tce_actual_per_day * overlap_days
                maintenance_allocated_this_period += pnl.maintenance_cost_allocated * ratio

            maintenance_pool = VoyagePnl._get_monthly_pool(
                rec.vessel_id,
                self.env.ref('vessel_voyage_pnl.cost_category_maintenance'),
                first, next_first,
            )
            idle_cost = max(maintenance_pool - maintenance_allocated_this_period, 0.0)

            calendar_days = (next_first - first).days

            rec.total_revenue = total_revenue
            rec.total_cost = total_cost
            rec.idle_cost_allocated = idle_cost
            rec.net_result = total_revenue - total_cost - idle_cost
            rec.calendar_days = calendar_days
            rec.voyage_days_total = voyage_days_total
            rec.utilization_pct = (
                (voyage_days_total / calendar_days) * 100.0 if calendar_days else 0.0
            )
            rec.avg_tce = (
                tce_weighted_sum / voyage_days_total if voyage_days_total else 0.0
            )

    def action_close(self):
        for rec in self:
            rec.state = 'closed'

    def action_reopen(self):
        for rec in self:
            rec.state = 'draft'

    @api.model
    def _cron_generate_vessel_pnl(self):
        """§4.3/§4.5 — bulanan tanggal 5, generate/update vessel.vessel.pnl bulan
        SEBELUMNYA (kasih waktu voyage bulan lalu selesai di-lock), per kapal aktif
        (kapal yang punya minimal 1 vessel.voyage.pnl)."""
        today = fields.Date.today()
        prev_month = today.month - 1 or 12
        prev_year = today.year - 1 if today.month == 1 else today.year
        vessel_ids = self.env['vessel.voyage.pnl'].search([]).mapped('vessel_id')
        for vessel in vessel_ids:
            existing = self.search([
                ('vessel_id', '=', vessel.id),
                ('period_month', '=', str(prev_month)),
                ('period_year', '=', prev_year),
            ], limit=1)
            if existing:
                if existing.state != 'closed':
                    existing._compute_totals()
            else:
                self.create({
                    'vessel_id': vessel.id,
                    'period_month': str(prev_month),
                    'period_year': prev_year,
                })
