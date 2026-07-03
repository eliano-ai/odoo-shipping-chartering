# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FleetVehicleVoyagePnl(models.Model):
    _inherit = 'fleet.vehicle'

    budget_variance_threshold_pct = fields.Float(
        string='Override Threshold Variance Budget (%)',
        help='Ambang batas variance budget vs actual khusus kapal ini. '
             'Kosongkan/0 untuk pakai default global perusahaan.',
    )
    voyage_pnl_ids = fields.One2many(
        'vessel.voyage.pnl', 'vessel_id', string='Riwayat Voyage P&L',
    )
    vessel_pnl_ids = fields.One2many(
        'vessel.vessel.pnl', 'vessel_id', string='Riwayat P&L Bulanan',
    )
    current_month_utilization_pct = fields.Float(
        string='Utilisasi Bulan Ini (%)', compute='_compute_current_month_utilization_pct',
    )

    def _compute_current_month_utilization_pct(self):
        today = fields.Date.context_today(self)
        for vehicle in self:
            pnl = vehicle.vessel_pnl_ids.filtered(
                lambda p: p.period_month == str(today.month) and p.period_year == today.year
            )[:1]
            vehicle.current_month_utilization_pct = pnl.utilization_pct if pnl else 0.0
