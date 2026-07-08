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

    # NB: field di res.config.settings TIDAK BOLEH diawali prefix "default_" —
    # itu reserved oleh Odoo untuk mekanisme ir.default (field wajib punya atribut
    # default_model), walau field ini murni related= biasa ke res.company. Trigger
    # Exception saat res.config.settings.default_get() dipanggil (lihat CLAUDE.md
    # Checklist Odoo 19 Gotcha).
    global_disbursement_variance_threshold_pct = fields.Float(
        related='company_id.default_disbursement_variance_threshold_pct', readonly=False,
        string='Default Threshold Variance PDA/FDA (%)',
    )
