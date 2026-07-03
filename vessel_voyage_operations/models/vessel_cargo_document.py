# -*- coding: utf-8 -*-
from odoo import fields, models

DOCUMENT_TYPE = [
    ('bl', 'Bill of Lading'),
    ('manifest', 'Manifest'),
    ('mate_receipt', "Mate's Receipt"),
    ('cargo_damage_report', 'Cargo Damage Report'),
    ('other', 'Other'),
]


class VesselCargoDocument(models.Model):
    _name = 'vessel.cargo.document'
    _description = 'Dokumen Kargo Voyage'
    _order = 'voyage_id, document_date desc, id desc'

    voyage_id = fields.Many2one(
        'vessel.voyage', string='Voyage', required=True, ondelete='cascade',
    )
    port_call_id = fields.Many2one(
        'vessel.port.call', string='Port Call',
        help='Opsional — link ke port call spesifik, mis. B/L terbit di load port.',
    )
    document_type = fields.Selection(DOCUMENT_TYPE, string='Tipe Dokumen', required=True)
    document_number = fields.Char(string='Nomor Dokumen')
    document_date = fields.Date(string='Tanggal Dokumen')
    qty_mt = fields.Float(
        string='Qty (MT)',
        help='Qty yang tercantum di dokumen — basis silang-cek bl_qty di vessel.charter.contract.',
    )
    attachment_ids = fields.Many2many('ir.attachment', string='Lampiran')
    notes = fields.Html(
        string='Catatan',
        help='Untuk cargo damage report: detail kerusakan.',
    )
    company_id = fields.Many2one(
        related='voyage_id.company_id', string='Perusahaan', store=True, readonly=True,
    )
