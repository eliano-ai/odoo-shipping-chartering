# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ResCurrencyRate(models.Model):
    _inherit = 'res.currency.rate'

    rate_source = fields.Selection(
        selection=[
            ('bi_jisdor', 'BI JISDOR'),
            ('manual', 'Manual'),
            ('internal', 'Internal'),
        ],
        string='Sumber Kurs',
        default='manual',
        required=True,
        help=(
            'Sumber data kurs ini.\n'
            'BI JISDOR: Kurs resmi Bank Indonesia '
            '(Jakarta Interbank Spot Dollar Rate).\n'
            'Manual: Diinput manual oleh tim accounting.\n'
            'Internal: Digenerate otomatis oleh sistem Odoo.'
        ),
    )

    rate_type = fields.Selection(
        selection=[
            ('closing', 'Closing Rate'),
            ('average_monthly', 'Average Rate Bulanan'),
            ('average_annual', 'Average Rate Tahunan'),
            ('transaction', 'Kurs Transaksi'),
        ],
        string='Tipe Kurs',
        default='closing',
        help='Kategori kurs untuk keperluan pelaporan.',
    )

    @api.constrains('rate', 'currency_id')
    def _check_rate_reasonable_idr(self):
        """
        Validasi kurs USD/IDR dalam range yang wajar (10.000–25.000).
        Hanya warning via chatter — tidak blocking.
        Konvensi Odoo 18: rate = jumlah IDR per 1 USD (market rate langsung
        jika company currency = IDR).
        """
        for record in self:
            if record.currency_id.name == 'USD' and record.rate > 0:
                if not (10_000 <= record.rate <= 25_000):
                    try:
                        record.message_post(
                            body=_(
                                'Peringatan: Kurs USD/IDR %.2f berada di luar '
                                'range yang umum (Rp 10.000 – Rp 25.000). '
                                'Pastikan nilai ini benar sebelum digunakan '
                                'untuk kalkulasi laporan.'
                            ) % record.rate
                        )
                    except Exception:
                        # message_post bisa gagal di beberapa konteks (e.g. test)
                        pass
