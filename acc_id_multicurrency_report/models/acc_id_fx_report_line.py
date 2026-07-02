# -*- coding: utf-8 -*-
from odoo import fields, models


class AccIdFxReportLine(models.Model):
    _name = 'acc.id.fx.report.line'
    _description = 'Baris Laporan Dual-Currency (Materialized)'
    _order = 'report_type, account_code'

    config_id = fields.Many2one(
        comodel_name='acc.id.fx.report.config',
        string='Config Laporan',
        required=True,
        ondelete='cascade',
        index=True,
    )

    calc_log_id = fields.Many2one(
        comodel_name='acc.id.fx.calc.log',
        string='Log Kalkulasi',
        readonly=True,
        help='Log run kalkulasi yang menghasilkan baris ini.',
    )

    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Akun',
        required=True,
        index=True,
    )

    account_code = fields.Char(
        string='Kode Akun',
        related='account_id.code',
        store=True,
    )

    account_name = fields.Char(
        string='Nama Akun',
        related='account_id.name',
        store=True,
    )

    account_type = fields.Selection(
        selection=[
            ('asset_receivable', 'Receivable'),
            ('asset_cash', 'Bank and Cash'),
            ('asset_current', 'Current Assets'),
            ('asset_non_current', 'Non-current Assets'),
            ('asset_prepayments', 'Prepayments'),
            ('asset_fixed', 'Fixed Assets'),
            ('liability_payable', 'Payable'),
            ('liability_credit_card', 'Credit Card'),
            ('liability_current', 'Current Liabilities'),
            ('liability_non_current', 'Non-current Liabilities'),
            ('equity', 'Equity'),
            ('equity_unaffected', 'Current Year Earnings'),
            ('income', 'Income'),
            ('income_other', 'Other Income'),
            ('expense', 'Expenses'),
            ('expense_other', 'Other Expenses'),
            ('expense_depreciation', 'Depreciation'),
            ('expense_direct_cost', 'Cost of Revenue'),
            ('off_balance', 'Off-Balance Sheet'),
        ],
        string='Tipe Akun',
        related='account_id.account_type',
        store=True,
    )

    report_type = fields.Selection(
        selection=[
            ('pl', 'Laba Rugi'),
            ('bs', 'Neraca'),
        ],
        string='Jenis Laporan',
        required=True,
        index=True,
    )

    balance_functional = fields.Float(
        string='Saldo IDR',
        digits=(16, 2),
        help='Saldo dalam mata uang fungsional (IDR).',
    )

    rate_type_applied = fields.Selection(
        selection=[
            ('average', 'Average Rate'),
            ('closing', 'Closing Rate'),
            ('historical', 'Historical Rate'),
            ('actual', 'Actual Rate'),
        ],
        string='Tipe Kurs Dipakai',
    )

    rate_used = fields.Float(
        string='Kurs Dipakai',
        digits=(16, 4),
        help='Market rate (IDR per USD) yang digunakan untuk baris ini.',
    )

    balance_presentation = fields.Float(
        string='Saldo USD',
        digits=(16, 2),
        help='Saldo ekuivalen dalam mata uang presentasi (USD).',
    )

    is_override = fields.Boolean(
        string='Kurs Override',
        default=False,
        help='True jika kurs diambil dari tabel override per akun.',
    )

    override_reason = fields.Text(
        string='Alasan Override',
    )
