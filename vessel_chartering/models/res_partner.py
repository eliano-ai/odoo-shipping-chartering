# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_port = fields.Boolean(
        string='Adalah Pelabuhan',
        help='Centang jika partner ini adalah pelabuhan (bisa dipakai sebagai load/discharge '
             'port di kontrak charter). Pelabuhan sering merangkap vendor/agent, karena itu '
             'tidak dibuat model terpisah.',
    )
    unlocode = fields.Char(
        string='UN/LOCODE',
        help="Kode pelabuhan internasional 5 karakter, misal 'IDTPP' untuk Tanjung Priok.",
    )
