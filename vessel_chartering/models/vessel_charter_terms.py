# -*- coding: utf-8 -*-
from odoo import fields, models


class VesselCharterTerms(models.Model):
    _name = 'vessel.charter.terms'
    _description = 'Template Terms Charter Party'
    _order = 'name'

    name = fields.Char(
        string='Nama Terms', required=True,
        help="Misal: 'FIOST 8,000/8,000 SHINC'",
    )
    loading_terms = fields.Char(
        string='Loading Terms',
        help='Misal: FIOST, FIOS, Berth Terms, dll.',
    )
    sundays_holidays_included = fields.Boolean(
        string='SHINC (Sundays/Holidays Included)',
        help='Centang jika Minggu & hari libur ikut dihitung sebagai laytime (SHINC). '
             'Kosongkan untuk SHEX (Sundays/Holidays Excluded).',
    )
    laytime_reversible_default = fields.Boolean(
        string='Laytime Reversible (Default)',
        help='Nilai default untuk field laytime_reversible di kontrak yang memakai terms ini.',
    )
    notes = fields.Html(string='Catatan')
    active = fields.Boolean(default=True)
