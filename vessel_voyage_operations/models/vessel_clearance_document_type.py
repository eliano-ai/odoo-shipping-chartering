# -*- coding: utf-8 -*-
from odoo import fields, models


class VesselClearanceDocumentType(models.Model):
    _name = 'vessel.clearance.document.type'
    _description = 'Tipe Dokumen Clearance Pelabuhan'
    _order = 'name'

    name = fields.Char(string='Nama', required=True, translate=True)
    default_required = fields.Boolean(
        string='Wajib Secara Default',
        help='Kalau dicentang, dokumen ini otomatis dibuat sebagai baris checklist wajib '
             'saat port call baru dibuat.',
    )
    active = fields.Boolean(default=True)
