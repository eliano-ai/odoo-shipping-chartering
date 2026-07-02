# -*- coding: utf-8 -*-
from odoo import fields, models


class VesselCargoType(models.Model):
    _name = 'vessel.cargo.type'
    _description = 'Tipe Kargo Kapal'
    _order = 'name'

    name = fields.Char(string='Nama Kargo', required=True, translate=True)
    is_dangerous = fields.Boolean(
        string='Kargo Berbahaya',
        help='Centang jika kargo termasuk dangerous goods (perlu penanganan khusus).',
    )
    default_stowage_factor = fields.Float(
        string='Stowage Factor Default (m3/ton)',
        help='Volume ruang muat yang dibutuhkan per ton kargo ini, untuk estimasi kapasitas.',
    )
    active = fields.Boolean(default=True)
