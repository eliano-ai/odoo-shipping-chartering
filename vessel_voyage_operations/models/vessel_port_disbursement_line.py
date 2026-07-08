# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class VesselPortDisbursementLine(models.Model):
    _name = 'vessel.port.disbursement.line'
    _description = 'Baris Item Port Disbursement (PDA/FDA)'
    _order = 'disbursement_id, id'

    disbursement_id = fields.Many2one(
        'vessel.port.disbursement', string='Disbursement', required=True, ondelete='cascade',
    )
    item_type_id = fields.Many2one(
        'vessel.disbursement.item.type', string='Tipe Item',
    )
    description = fields.Char(string='Deskripsi')
    currency_id = fields.Many2one(
        related='disbursement_id.currency_id', string='Mata Uang', readonly=True,
    )
    amount = fields.Monetary(string='Jumlah', currency_field='currency_id')

    @api.depends('disbursement_id.display_name', 'item_type_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('%(disb)s — %(item)s') % {
                'disb': rec.disbursement_id.display_name or _('Disbursement'),
                'item': rec.item_type_id.name or _('Item'),
            }
