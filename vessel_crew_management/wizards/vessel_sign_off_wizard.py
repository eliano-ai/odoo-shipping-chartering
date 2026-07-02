from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import date


class VesselSignOffWizard(models.TransientModel):
    _name = 'vessel.sign.off.wizard'
    _description = 'Wizard Sign Off ABK'

    assignment_id = fields.Many2one(
        'vessel.crew.assignment', string='Penugasan',
        required=True, readonly=True,
    )
    seafarer_name = fields.Char(
        related='assignment_id.seafarer_id.name',
        string='ABK', readonly=True,
    )
    vessel_name = fields.Char(
        related='assignment_id.vehicle_id.name',
        string='Kapal', readonly=True,
    )
    sign_on_actual_date = fields.Date(
        related='assignment_id.sign_on_actual_date',
        string='Tanggal Sign On', readonly=True,
    )
    sign_off_date = fields.Date(
        string='Tanggal Sign Off (Aktual)',
        required=True, default=fields.Date.today,
    )
    sign_off_port = fields.Char(
        string='Pelabuhan Sign Off', required=True,
    )
    sign_off_reason = fields.Selection(
        [
            ('end_of_contract', 'Selesai Kontrak'),
            ('medical', 'Alasan Medis'),
            ('personal', 'Alasan Pribadi'),
            ('emergency', 'Keadaan Darurat'),
            ('termination', 'Pemutusan Hubungan Kerja'),
            ('repatriation', 'Repatriasi'),
            ('other', 'Lainnya'),
        ],
        string='Alasan Sign Off',
        required=True, default='end_of_contract',
    )
    sea_service_days_preview = fields.Integer(
        string='Total Hari di Laut',
        compute='_compute_preview',
    )
    notes = fields.Text(string='Catatan Tambahan')

    @api.depends('assignment_id', 'sign_off_date')
    def _compute_preview(self):
        for rec in self:
            sign_on = rec.assignment_id.sign_on_actual_date
            if sign_on and rec.sign_off_date:
                rec.sea_service_days_preview = (rec.sign_off_date - sign_on).days
            else:
                rec.sea_service_days_preview = 0

    @api.constrains('sign_off_date')
    def _check_sign_off_date(self):
        for rec in self:
            sign_on = rec.assignment_id.sign_on_actual_date
            if sign_on and rec.sign_off_date < sign_on:
                raise ValidationError(_(
                    "Tanggal sign off tidak boleh sebelum tanggal sign on (%s)."
                ) % sign_on)

    def action_confirm_sign_off(self):
        self.ensure_one()
        self.assignment_id._do_sign_off(
            sign_off_date=self.sign_off_date,
            sign_off_port=self.sign_off_port,
            reason=self.sign_off_reason,
            notes=self.notes or '',
        )
        return {'type': 'ir.actions.act_window_close'}
