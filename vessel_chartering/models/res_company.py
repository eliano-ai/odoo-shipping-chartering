# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    despatch_as_credit_note = fields.Boolean(
        string='Despatch sebagai Credit Note',
        default=False,
        help='Jika dicentang, despatch dibuat sebagai credit note terpisah. '
             'Jika tidak, despatch dibuat sebagai invoice line dengan nilai negatif.',
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    despatch_as_credit_note = fields.Boolean(
        related='company_id.despatch_as_credit_note', readonly=False,
        string='Despatch sebagai Credit Note',
    )
