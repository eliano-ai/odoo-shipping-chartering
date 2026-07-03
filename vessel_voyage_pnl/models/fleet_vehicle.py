# -*- coding: utf-8 -*-
from odoo import fields, models


class FleetVehicleVoyagePnl(models.Model):
    _inherit = 'fleet.vehicle'

    budget_variance_threshold_pct = fields.Float(
        string='Override Threshold Variance Budget (%)',
        help='Ambang batas variance budget vs actual khusus kapal ini. '
             'Kosongkan/0 untuk pakai default global perusahaan.',
    )
