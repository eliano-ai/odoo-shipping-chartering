# -*- coding: utf-8 -*-
from odoo import fields, models

INDEX_NAME = [
    ('mops', 'MOPS'),
    ('platts', 'Platts'),
    ('other', 'Other'),
]


class VesselBunkerPriceReference(models.Model):
    _name = 'vessel.bunker.price.reference'
    _description = 'Referensi Harga Bunker (MOPS/Platts)'
    _order = 'date desc'

    date = fields.Date(required=True)
    index_name = fields.Selection(INDEX_NAME, required=True, default='mops')
    fuel_type_id = fields.Many2one(
        'fleet.fuel.type', string='Jenis Bahan Bakar', required=True,
        help='Reuse master fleet.fuel.type dari fleet_fuel_log — tidak ada master baru.',
    )
    price_usd_mt = fields.Float(string='Harga (USD/MT)', required=True)
    region = fields.Char(help='Opsional — harga bisa beda per region (Singapore, Jakarta, dll).')
