# -*- coding: utf-8 -*-
from odoo import fields, models

CATEGORY_GROUP = [
    ('revenue', 'Revenue'),
    ('direct_cost', 'Direct Cost'),
    ('allocated_cost', 'Allocated Cost'),
]


class VesselPnlCostCategory(models.Model):
    _name = 'vessel.pnl.cost.category'
    _description = 'Kategori Biaya P&L Voyage/Kapal'
    _order = 'category_group, sequence, name'

    name = fields.Char(required=True)
    category_group = fields.Selection(CATEGORY_GROUP, required=True)
    default_account_ids = fields.Many2many(
        'account.account', string='Akun Default',
        help='Untuk mapping otomatis saat mengkategorikan account.move.line yang '
             'tidak berasal dari modul terstruktur (mis. cargo handling dari vendor bill manual).',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
