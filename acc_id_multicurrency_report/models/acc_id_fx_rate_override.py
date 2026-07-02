# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccIdFxRateOverride(models.Model):
    _name = 'acc.id.fx.rate.override'
    _description = 'Override Kurs per Akun untuk Laporan Dual-Currency'

    config_id = fields.Many2one(
        comodel_name='acc.id.fx.report.config',
        string='Config Laporan',
        required=True,
        ondelete='cascade',
        index=True,
    )

    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Akun',
        required=True,
        domain="[('company_ids', 'in', [parent.company_id])]",
    )

    rate_type_override = fields.Selection(
        selection=[
            ('average', 'Average Rate (dari config)'),
            ('closing', 'Closing Rate (dari config)'),
            ('historical', 'Historical Rate (Phase 3)'),
            ('manual', 'Kurs Manual (isi nilai di bawah)'),
        ],
        string='Tipe Kurs Override',
        required=True,
    )

    manual_rate = fields.Float(
        string='Kurs Manual (IDR per USD)',
        digits=(16, 4),
        help='Isi hanya jika Tipe Kurs = Manual. Contoh: 16000.00',
    )

    reason = fields.Text(
        string='Alasan Override',
        required=True,
        help='Wajib diisi untuk keperluan audit trail.',
    )

    @api.constrains('rate_type_override', 'manual_rate')
    def _check_manual_rate(self):
        for rec in self:
            if rec.rate_type_override == 'manual':
                if not rec.manual_rate or rec.manual_rate <= 0:
                    raise ValidationError(_(
                        'Kurs manual harus diisi dan lebih besar dari 0 '
                        'jika tipe kurs adalah "Kurs Manual".'
                    ))

    @api.constrains('config_id', 'account_id')
    def _check_unique_account_per_config(self):
        for rec in self:
            duplicate = self.search([
                ('config_id', '=', rec.config_id.id),
                ('account_id', '=', rec.account_id.id),
                ('id', '!=', rec.id),
            ])
            if duplicate:
                raise ValidationError(_(
                    'Akun "%s" sudah memiliki override kurs untuk laporan ini.'
                ) % rec.account_id.display_name)
