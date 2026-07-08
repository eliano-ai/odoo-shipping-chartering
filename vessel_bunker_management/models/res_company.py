# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    default_bunker_variance_threshold_pct = fields.Float(
        string='Default Threshold Variance ROB (%)',
        default=8.0,
        help='Ambang batas variance ROB reconciliation global (persen), dipakai untuk '
             'kapal yang tidak punya override threshold sendiri.',
    )
    default_bdn_survey_tolerance_pct = fields.Float(
        string='Default Toleransi Survey BDN (%)',
        default=0.5,
        help='Ambang batas selisih qty BDN vs independent survey sebelum dianggap dispute.',
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # NB: field di res.config.settings TIDAK BOLEH diawali prefix "default_" —
    # itu reserved oleh Odoo untuk mekanisme ir.default (field wajib punya atribut
    # default_model), walau field ini murni related= biasa ke res.company. Trigger
    # Exception saat res.config.settings.default_get() dipanggil (lihat CLAUDE.md
    # Checklist Odoo 19 Gotcha).
    global_bunker_variance_threshold_pct = fields.Float(
        related='company_id.default_bunker_variance_threshold_pct', readonly=False,
        string='Default Threshold Variance ROB (%)',
    )
    global_bdn_survey_tolerance_pct = fields.Float(
        related='company_id.default_bdn_survey_tolerance_pct', readonly=False,
        string='Default Toleransi Survey BDN (%)',
    )
