# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

DIRECTION = [
    ('in', 'Masuk'),
    ('out', 'Keluar'),
]

STATUS = [
    ('pending', 'Pending'),
    ('submitted', 'Submitted'),
    ('cleared', 'Cleared'),
    ('rejected', 'Rejected'),
]


class VesselPortClearanceLine(models.Model):
    _name = 'vessel.port.clearance.line'
    _description = 'Baris Checklist Clearance Dokumen Pelabuhan'
    _order = 'port_call_id, direction, id'

    port_call_id = fields.Many2one(
        'vessel.port.call', string='Port Call', required=True, ondelete='cascade',
    )
    document_type_id = fields.Many2one(
        'vessel.clearance.document.type', string='Tipe Dokumen', required=True,
    )
    direction = fields.Selection(DIRECTION, string='Arah', required=True, default='in')
    status = fields.Selection(
        STATUS, string='Status', default='pending', required=True,
    )
    cleared_date = fields.Datetime(string='Tanggal Cleared')
    document_number = fields.Char(string='Nomor Dokumen')
    attachment_ids = fields.Many2many('ir.attachment', string='Lampiran')

    @api.depends('port_call_id.display_name', 'document_type_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('%(call)s — %(doc)s') % {
                'call': rec.port_call_id.display_name or _('Port Call'),
                'doc': rec.document_type_id.name or _('Dokumen'),
            }
