# -*- coding: utf-8 -*-
{
    'name': 'Maritime',
    'version': '19.0.1.0.0',
    'category': 'Fleet Management',
    'summary': 'App root untuk modul komersial pelayaran: Chartering & Voyage Operations',
    'description': """
Maritime — App Root Komersial Pelayaran
=========================================
Menyatukan modul-modul komersial pelayaran (chartering, voyage operations,
dan modul lanjutan di masa depan seperti voyage P&L, bunker management)
ke dalam satu app terpisah dari Fleet (yang fokus ke asset management fisik
kendaraan darat & kapal — dokumen legal, BBM, maintenance, sparepart, ABK).

Modul ini murni container/app root — tidak ada model baru, hanya menyatukan
menu root vessel_chartering dan vessel_voyage_operations di bawah app baru
"Maritime" (sebelumnya keduanya menjadi submenu di app Fleet).
    """,
    'author': 'Sunartha ERP Consulting',
    'website': 'https://www.sunartha.co.id',
    'license': 'LGPL-3',
    'depends': [
        'vessel_chartering',
        'vessel_voyage_operations',
    ],
    'data': [
        'views/maritime_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
