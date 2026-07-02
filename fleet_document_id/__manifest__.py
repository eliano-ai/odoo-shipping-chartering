{
    'name': 'Fleet Document Management ID',
    'version': '19.0.2.0.0',
    'category': 'Fleet',
    'summary': 'Manajemen dokumen legal kendaraan darat dan kapal laut Indonesia (STNK, SIM, BKI, Sijil, STCW, SPB, dll)',
    'description': """
Fleet Document Management Indonesia
====================================
Modul custom untuk manajemen dokumen legal kendaraan operasional di Indonesia.

Fitur:
- Tracking STNK, BPKB, KIR, SIM, Asuransi, Uji Emisi, Dispensasi Tonase
- Alert otomatis H-30, H-7, H-0, H+7 sebelum/setelah expired
- Validasi SIM pengemudi saat assignment ke kendaraan
- Wizard perpanjangan dokumen dengan audit trail lengkap
- Dashboard compliance terpusat
- Laporan PDF compliance summary
- Integrasi dengan fleet, hr, account, mail
    """,
    'author': 'Sunartha ERP Consulting',
    'website': 'https://sunartha.co.id',
    'license': 'LGPL-3',
    'depends': [
        'fleet',
        'hr',
        'account',
        'mail',
        'hr_expense',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/fleet_document_security.xml',
        'data/fleet_document_data.xml',
        'data/fleet_document_vessel_data.xml',
        'data/fleet_document_cron.xml',
        'data/fleet_document_mail_template.xml',
        'views/fleet_document_type_views.xml',
        'views/fleet_vehicle_document_views.xml',
        'views/fleet_vehicle_views.xml',
        'views/fleet_document_dashboard_views.xml',
        'views/fleet_document_menus.xml',
        'wizards/fleet_document_renewal_wizard_views.xml',
        'report/fleet_document_compliance_report.xml',
        'report/fleet_document_compliance_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'fleet_document_id/static/src/js/fleet_document_widget.js',
            'fleet_document_id/static/src/css/fleet_document.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
