from odoo import api, fields, models, _


class FleetDocumentRenewalLog(models.Model):
    _name = 'fleet.document.renewal.log'
    _description = 'Riwayat Perpanjangan Dokumen Kendaraan'
    _order = 'renewal_date desc'

    document_id = fields.Many2one(
        'fleet.vehicle.document', string='Dokumen',
        required=True, ondelete='cascade', index=True,
    )
    vehicle_id = fields.Many2one(
        related='document_id.vehicle_id', string='Kendaraan', store=True,
    )
    doc_type = fields.Selection(
        related='document_id.doc_type', string='Jenis Dokumen', store=True,
    )
    renewal_date = fields.Date(
        string='Tanggal Perpanjangan',
        required=True, default=fields.Date.today,
    )
    previous_expiry_date = fields.Date(string='Expired Sebelumnya')
    new_expiry_date = fields.Date(string='Expired Baru', required=True)
    cost = fields.Monetary(
        string='Biaya Perpanjangan',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency', string='Mata Uang',
        default=lambda self: self.env.ref('base.IDR', raise_if_not_found=False),
    )
    renewed_by = fields.Many2one(
        'res.users', string='Diproses Oleh',
        default=lambda self: self.env.user,
    )
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Scan Dokumen Baru',
        help='Upload scan / foto dokumen hasil perpanjangan',
    )
    note = fields.Text(string='Catatan')
    expense_id = fields.Many2one(
        'hr.expense', string='Expense Terkait',
        help='Expense yang dibuat otomatis dari biaya perpanjangan ini',
    )
    company_id = fields.Many2one(
        'res.company', related='document_id.company_id', store=True,
    )
