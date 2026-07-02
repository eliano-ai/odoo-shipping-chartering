# -*- coding: utf-8 -*-
{
    'name': 'Sunartha ID — Multi-Currency Financial Reporting',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Laporan keuangan dual-column IDR+USD untuk manajemen',
    'description': """
Sunartha ID Basic Package — Multi-Currency Financial Reporting
==============================================================

Menyediakan laporan Laba Rugi dan Neraca dalam dua kolom:
- IDR (mata uang fungsional)
- USD (ekuivalen presentasi manajemen)

Fitur Phase 1:
- Dual-column P&L Report
- Dual-column Balance Sheet
- Materialized calculation dengan audit log immutable
- Warning system (stale detection)
- Drill-down ke level transaksi (lazy load + pagination)
- Export XLSX (3 sheet: P&L, Neraca, Info Kurs)
- CFO View dan Accounting View
- Rate override per akun
- Disclaimer PSAK 10 otomatis

Referensi: FSD_acc_id_multicurrency_report_v1.0.md
    """,
    'author': 'Sunartha',
    'website': 'https://www.sunartha.co.id',
    'license': 'OPL-1',
    'depends': [
        'account',
        'account_accountant',
        'l10n_id',
    ],
    'data': [
        # Security — harus pertama
        'security/acc_id_fx_security.xml',
        'security/ir.model.access.csv',
        # Data default
        'data/acc_id_fx_account_defaults.xml',
        # Views
        'views/res_currency_rate_views.xml',
        'views/account_account_views.xml',
        'views/acc_id_fx_report_config_views.xml',
        'views/acc_id_fx_calc_log_views.xml',
        'views/fx_menu.xml',
        # Wizard
        'wizard/fx_report_wizard_views.xml',
        # Reports (QWeb templates)
        'report/fx_pl_report.xml',
        'report/fx_bs_report.xml',
        # XLSX report action
        'report/fx_xlsx_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'acc_id_multicurrency_report/static/src/js/fx_report.js',
            'acc_id_multicurrency_report/static/src/css/fx_report.css',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
