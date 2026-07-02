# -*- coding: utf-8 -*-
{
    'name': 'Fleet Fuel Log & Consumption Tracking',
    'version': '19.0.1.0.0',
    'category': 'Fleet',
    'summary': 'Pencatatan BBM, konsumsi, trip/voyage, integrasi Inventory & Accounting',
    'description': """
Fleet Fuel Log & Consumption Tracking
======================================
Fitur:
- Master jenis BBM (Solar/HSD, MFO, dsb.) dengan harga & produk Inventory
- 3 tipe transaksi: Pengisian (Refuel), Pemakaian Harian, Per Trip/Voyage
- Workflow approval: Draft → To Approve → Approved → Posted
- Auto-compute konsumsi (L/100km) per log
- Anomaly detection: spike konsumsi → email Fleet Manager otomatis
- Integrasi Inventory: stock.move konsumsi BBM saat Approved
- Integrasi Accounting: journal entry biaya BBM saat Posted
- Model Trip/Voyage: kumpulkan fuel log per perjalanan
- Laporan: pivot cost, grafik trend, perbandingan antar kendaraan
- Tab Fuel di form kendaraan dengan smart button & statistik
    """,
    'author': 'Custom Development',
    'depends': [
        'fleet',
        'stock',
        'account',
        'mail',
        'uom',
    ],
    'data': [
        'security/fleet_fuel_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/fleet_fuel_type_data.xml',
        'data/ir_cron_data.xml',
        'views/fleet_fuel_type_views.xml',
        'views/fleet_fuel_log_views.xml',
        'views/fleet_vehicle_trip_views.xml',
        'views/fleet_vehicle_views.xml',
        'views/fleet_fuel_log_menu.xml',
        'report/fleet_fuel_report_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
