# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    default_budget_variance_threshold_pct = fields.Float(
        string='Default Threshold Variance Budget (%)',
        default=20.0,
        help='Ambang batas variance budget vs actual global (dalam persen), dipakai untuk '
             'kapal yang tidak punya override threshold sendiri.',
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    default_budget_variance_threshold_pct = fields.Float(
        related='company_id.default_budget_variance_threshold_pct', readonly=False,
        string='Default Threshold Variance Budget (%)',
    )
