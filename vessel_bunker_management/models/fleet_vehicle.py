# -*- coding: utf-8 -*-
from odoo import fields, models


class FleetVehicleBunkerManagement(models.Model):
    _inherit = 'fleet.vehicle'

    bunker_variance_threshold_pct = fields.Float(
        string='Override Threshold Variance ROB (%)',
        help='Ambang batas variance ROB reconciliation khusus kapal ini. '
             'Kosongkan/0 untuk pakai default global perusahaan.',
    )
