from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FleetDocumentRenewalWizard(models.TransientModel):
    _name = 'fleet.document.renewal.wizard'
    _description = 'Wizard Perpanjangan Dokumen Kendaraan'

    document_id = fields.Many2one(
        'fleet.vehicle.document', string='Dokumen',
        required=True, readonly=True,
    )
    vehicle_id = fields.Many2one(
        related='document_id.vehicle_id', string='Kendaraan', readonly=True,
    )
    doc_type = fields.Selection(
        related='document_id.doc_type', string='Jenis Dokumen', readonly=True,
    )
    current_expiry = fields.Date(
        string='Expired Saat Ini',
        related='document_id.expiry_date', readonly=True,
    )
    renewal_date = fields.Date(
        string='Tanggal Pengurusan',
        required=True, default=fields.Date.today,
    )
    new_expiry_date = fields.Date(
        string='Berlaku Hingga (Baru)',
        required=True,
        help='Masukkan tanggal berlaku dokumen setelah diperpanjang',
    )
    new_doc_number = fields.Char(
        string='Nomor Dokumen Baru',
        help='Isi jika nomor dokumen berubah setelah perpanjangan',
    )
    cost = fields.Monetary(
        string='Biaya Perpanjangan',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency', string='Mata Uang',
        default=lambda self: self.env.ref('base.IDR', raise_if_not_found=False),
    )
    create_expense = fields.Boolean(
        string='Buat Expense Otomatis',
        default=False,
        help='Jika dicentang, sistem akan membuat draft hr.expense dari biaya perpanjangan ini',
    )
    expense_employee_id = fields.Many2one(
        'hr.employee', string='Karyawan (Expense)',
        help='Karyawan yang mengajukan expense perpanjangan dokumen',
    )
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Upload Dokumen Baru',
        help='Scan / foto dokumen hasil perpanjangan (PDF, JPG, PNG)',
    )
    note = fields.Text(
        string='Catatan',
        help='Nomor antrian, nama petugas, nama agen asuransi, dll',
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Constraints
    # ─────────────────────────────────────────────────────────────────────────

    @api.constrains('new_expiry_date', 'current_expiry')
    def _check_new_expiry(self):
        for rec in self:
            if rec.current_expiry and rec.new_expiry_date <= rec.current_expiry:
                raise ValidationError(_(
                    "Tanggal berlaku baru (%s) harus lebih besar dari "
                    "tanggal berlaku saat ini (%s)."
                ) % (rec.new_expiry_date, rec.current_expiry))

    @api.constrains('new_expiry_date', 'renewal_date')
    def _check_dates_order(self):
        for rec in self:
            if rec.new_expiry_date <= rec.renewal_date:
                raise ValidationError(_(
                    "Tanggal berlaku baru harus lebih besar dari tanggal pengurusan."
                ))

    # ─────────────────────────────────────────────────────────────────────────
    # Main action
    # ─────────────────────────────────────────────────────────────────────────

    def action_confirm_renewal(self):
        self.ensure_one()
        doc = self.document_id

        # 1. Create renewal log
        log_vals = {
            'document_id': doc.id,
            'renewal_date': self.renewal_date,
            'previous_expiry_date': doc.expiry_date,
            'new_expiry_date': self.new_expiry_date,
            'cost': self.cost,
            'currency_id': self.currency_id.id,
            'renewed_by': self.env.user.id,
            'note': self.note,
        }
        if self.attachment_ids:
            log_vals['attachment_ids'] = [(6, 0, self.attachment_ids.ids)]
        renewal_log = self.env['fleet.document.renewal.log'].create(log_vals)

        # 2. Update document record
        update_vals = {
            'expiry_date': self.new_expiry_date,
            'renewal_cost': self.cost,
        }
        if self.new_doc_number:
            update_vals['doc_number'] = self.new_doc_number
        if self.attachment_ids:
            update_vals['attachment_ids'] = [(4, att.id) for att in self.attachment_ids]
        doc.write(update_vals)

        # 3. Create expense if requested
        if self.create_expense and self.cost and self.expense_employee_id:
            expense_product = self.env.ref(
                'fleet_document_id.product_fleet_doc_renewal',
                raise_if_not_found=False,
            )
            expense_vals = {
                'name': _('Perpanjangan %s — %s') % (
                    doc.display_name,
                    self.renewal_date.strftime('%d/%m/%Y'),
                ),
                'employee_id': self.expense_employee_id.id,
                'total_amount': self.cost,
                'currency_id': self.currency_id.id,
                'date': self.renewal_date,
                'product_id': expense_product.id if expense_product else False,
                'quantity': 1.0,
            }
            expense = self.env['hr.expense'].create(expense_vals)
            renewal_log.expense_id = expense.id

        # 4. Post to chatter
        doc.message_post(
            body=_(
                "Dokumen diperpanjang oleh %s pada %s.<br/>"
                "Expired baru: <strong>%s</strong>%s"
            ) % (
                self.env.user.name,
                self.renewal_date.strftime('%d/%m/%Y'),
                self.new_expiry_date.strftime('%d/%m/%Y'),
                (' | Biaya: Rp {:,.0f}'.format(self.cost)) if self.cost else '',
            ),
            subtype_xmlid='mail.mt_note',
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Perpanjangan Berhasil'),
                'message': _(
                    'Dokumen %s berhasil diperpanjang hingga %s.'
                ) % (doc.display_name, self.new_expiry_date.strftime('%d/%m/%Y')),
                'type': 'success',
                'sticky': False,
            },
        }
