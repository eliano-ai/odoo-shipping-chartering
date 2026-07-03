# -*- coding: utf-8 -*-
from odoo import fields, models


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
