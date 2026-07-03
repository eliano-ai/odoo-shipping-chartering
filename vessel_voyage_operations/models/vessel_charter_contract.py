# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class VesselCharterContractVoyageOperations(models.Model):
    _inherit = 'vessel.charter.contract'

    voyage_ids = fields.One2many(
        'vessel.voyage', 'charter_contract_id', string='Voyages',
    )
    voyage_count = fields.Integer(string='Jumlah Voyage', compute='_compute_voyage_count')

    @api.depends('voyage_ids')
    def _compute_voyage_count(self):
        for rec in self:
            rec.voyage_count = len(rec.voyage_ids)

    def action_view_voyages(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Voyages — %s') % self.name,
            'res_model': 'vessel.voyage',
            'view_mode': 'list,form',
            'domain': [('charter_contract_id', '=', self.id)],
            'context': {'default_charter_contract_id': self.id},
        }
