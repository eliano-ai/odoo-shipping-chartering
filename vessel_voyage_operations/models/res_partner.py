# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_port_agent = fields.Boolean(
        string='Adalah Agen Pelabuhan',
        help="Centang jika partner ini berperan sebagai agen pelabuhan (mengurus PDA/FDA, "
             "clearance dokumen kapal). Beda dari 'Adalah Pelabuhan' (is_port) — satu partner "
             "bisa jadi pelabuhan sekaligus agen, tapi umumnya dua peran terpisah (pelabuhan vs "
             "perusahaan agensi yang beroperasi di pelabuhan tsb).",
    )
    disbursement_variance_threshold_pct = fields.Float(
        string='Threshold Variance PDA/FDA (%)',
        help='Ambang batas variance PDA vs FDA (dalam persen) khusus untuk agen ini. '
             'Kosongkan/isi 0 untuk memakai default global perusahaan '
             '(Pengaturan > Voyage Operations).',
    )
