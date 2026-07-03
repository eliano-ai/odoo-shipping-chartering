# -*- coding: utf-8 -*-
from odoo import api, fields, models


class VesselHireStatementLineBunkerManagement(models.Model):
    _inherit = 'vessel.hire.statement.line'

    bod_bor_id = fields.Many2one(
        'vessel.bunker.bod.bor', string='Sumber BOD/BOR', compute='_compute_bod_bor_id',
    )

    @api.depends('contract_id.bod_bor_ids.hire_statement_line_id')
    def _compute_bod_bor_id(self):
        for line in self:
            rec = line.contract_id.bod_bor_ids.filtered(
                lambda b: b.hire_statement_line_id == line
            )[:1]
            line.bod_bor_id = rec
