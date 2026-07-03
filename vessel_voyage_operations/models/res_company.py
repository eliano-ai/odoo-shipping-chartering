# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    default_disbursement_variance_threshold_pct = fields.Float(
        string='Default Threshold Variance PDA/FDA (%)',
        default=15.0,
        help='Ambang batas variance PDA vs FDA global (dalam persen), dipakai untuk agen '
             'pelabuhan yang tidak punya override threshold sendiri.',
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    default_disbursement_variance_threshold_pct = fields.Float(
        related='company_id.default_disbursement_variance_threshold_pct', readonly=False,
        string='Default Threshold Variance PDA/FDA (%)',
    )
