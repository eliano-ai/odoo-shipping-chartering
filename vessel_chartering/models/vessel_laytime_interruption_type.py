# -*- coding: utf-8 -*-
from odoo import fields, models


class VesselLaytimeInterruptionType(models.Model):
    _name = 'vessel.laytime.interruption.type'
    _description = 'Tipe Interupsi Laytime'
    _order = 'name'

    name = fields.Char(string='Nama Interupsi', required=True, translate=True)
    is_counting = fields.Boolean(
        string='Tetap Dihitung sebagai Laytime',
        default=False,
        help='Jika dicentang, waktu selama interupsi ini tetap dihitung sebagai laytime used '
             '(counting). Jika tidak, waktu ini dikecualikan — kecuali sudah melewati titik '
             'on-demurrage (aturan "once on demurrage, always on demurrage").',
    )
    active = fields.Boolean(default=True)
