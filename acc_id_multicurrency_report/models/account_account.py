# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = 'account.account'

    id_fx_rate_type = fields.Selection(
        selection=[
            ('average', 'Average Rate (pendapatan/beban)'),
            ('closing', 'Closing Rate (aset/liabilitas)'),
            ('historical', 'Historical Rate (Phase 3 — non-monetary)'),
            ('actual', 'Actual Rate (selisih kurs)'),
        ],
        string='Tipe Kurs FX',
        default=False,
        help=(
            'Menentukan jenis kurs yang dipakai untuk akun ini '
            'saat kalkulasi laporan dual-currency.\n\n'
            'Kosongkan untuk menggunakan default otomatis '
            'berdasarkan tipe akun:\n'
            '- Pendapatan/Beban → Average Rate\n'
            '- Aset/Liabilitas/Ekuitas → Closing Rate'
        ),
    )

    id_exclude_from_fx = fields.Boolean(
        string='Kecualikan dari Kalkulasi FX',
        default=False,
        help=(
            'Centang untuk mengecualikan akun ini dari laporan '
            'dual-currency. Gunakan untuk akun statistik, akun '
            'teknikal, atau akun yang tidak relevan untuk pelaporan.'
        ),
    )

    def _get_effective_fx_rate_type(self):
        """
        Mengembalikan tipe kurs efektif untuk akun ini.

        Urutan prioritas:
        1. Field id_fx_rate_type jika diisi eksplisit
        2. Default berdasarkan account_type (Odoo 18)
        3. Fallback aman: 'closing'

        Return: str — salah satu dari 'average', 'closing', 'historical', 'actual'
        """
        self.ensure_one()

        if self.id_fx_rate_type:
            return self.id_fx_rate_type

        # Grup account_type berdasarkan Odoo 18
        _INCOME_TYPES = frozenset({'income', 'income_other'})
        _EXPENSE_TYPES = frozenset({
            'expense', 'expense_depreciation', 'expense_direct_cost',
        })

        if self.account_type in _INCOME_TYPES | _EXPENSE_TYPES:
            return 'average'

        # Semua tipe aset, liabilitas, ekuitas → closing
        return 'closing'
