# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    charter_contract_id = fields.Many2one(
        'vessel.charter.contract', string='Charter Contract',
        readonly=True, copy=False, index=True,
    )
