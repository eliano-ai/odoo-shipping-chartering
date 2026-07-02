# -*- coding: utf-8 -*-
{
    'name': 'Fleet Maintenance Schedule',
    'version': '19.0.1.0.0',
    'category': 'Fleet',
    'summary': 'Jadwal maintenance kendaraan terintegrasi dengan Maintenance, Inventory & Calendar',
    'description': """
Fleet Maintenance Schedule
==========================
Modul custom untuk menjadwalkan dan melacak maintenance kendaraan armada.

Fitur:
- Tab Maintenance Schedule di form kendaraan (fleet.vehicle)
- 4 tipe maintenance: Preventive, Corrective, Predictive, Overhaul
- Trigger ganda: tanggal & odometer/jam mesin
- Workflow: Draft → Confirmed → In Progress → Done
- Auto-create Maintenance Request saat Confirmed
- Konsumsi spare parts terintegrasi Inventory (stock.picking)
- Reminder email otomatis via ir.cron
- Activity (Calendar) terintegrasi
- Hak akses: Fleet Manager (full) & Maintenance Technician (terbatas)
    """,
    'author': 'Custom Development',
    'depends': [
        'fleet',
        'maintenance',
        'stock',
        'mail',
    ],
    'data': [
        'security/fleet_maintenance_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'views/fleet_maintenance_schedule_views.xml',
        'views/fleet_vehicle_views.xml',
        'views/fleet_maintenance_schedule_menu.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
