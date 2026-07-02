{
    'name': 'Vessel Crew Management',
    'version': '19.0.1.1.0',
    'summary': 'Sign on/off, STCW cert validation, scheduling & notifications untuk ABK kapal laut',
    'description': """
Vessel Crew Management — MVP
=============================
Modul manajemen ABK kapal laut untuk perusahaan pelayaran Indonesia.

Fitur MVP:
- Master data seafarer (extend hr.employee)
- Master rank / jabatan ABK
- Sign on / sign off log dengan state machine
- Validasi sertifikat STCW saat sign on
- Sea service log otomatis
- Manning list real-time per kapal
- Crew scheduling + rotation plan
- Notifikasi email & WhatsApp (via WA gateway)
- Dashboard compliance sederhana

Regulasi: STCW 1978 (Manila 2010), MLC 2006, Ditjen Hubla Indonesia
    """,
    'author': 'Sunartha ERP Consulting',
    'website': 'https://www.sunartha.co.id',
    'license': 'LGPL-3',
    'category': 'Fleet Management',
    'depends': [
        'fleet',
        'hr',
        'mail',
        'calendar',
        'fleet_document_id',
    ],
    'data': [
        'security/vessel_crew_security.xml',
        'security/ir.model.access.csv',
        'data/vessel_crew_rank_data.xml',
        'data/vessel_crew_cron.xml',
        'data/vessel_crew_mail_template.xml',
        'views/vessel_seafarer_views.xml',
        'views/vessel_crew_rank_views.xml',
        'views/vessel_crew_assignment_views.xml',
        'views/vessel_crew_schedule_views.xml',
        'views/vessel_fleet_vehicle_inherit_views.xml',
        'views/vessel_crew_menus.xml',
        'wizards/vessel_sign_off_wizard_views.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
