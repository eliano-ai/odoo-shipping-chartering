# -*- coding: utf-8 -*-
{
    'name': 'Vessel Bunker Management',
    'version': '19.0.1.0.0',
    'category': 'Fleet Management',
    'summary': 'Procurement bunker, BDN & independent survey, ROB reconciliation, BOD/BOR settlement',
    'description': """
Vessel Bunker Management — Layer 3 Finansial (#4)
====================================================
Bunker adalah 40-60% biaya voyage sekaligus celah fraud terbesar di industri
pelayaran. Modul ini menutup tiga celah sekaligus: procurement terstruktur,
independent survey vs BDN (dispute tracking), dan ROB reconciliation
(noon report vs supply vs consumption) — memperkuat anomaly detection
fleet_fuel_log dengan sumber silang independen.

Fitur MVP (lihat TECH_SPEC_vessel_bunker_management.md untuk detail lengkap):
- Bunker procurement: inquiry -> quote comparison -> nominasi -> PO otomatis
- BDN (Bunker Delivery Note) + independent survey + dispute tracking
- ROB reconciliation (previous ROB + supply - consumption vs actual)
- BOD/BOR settlement otomatis ke hire statement (Time Charter)
- Price reference tracking (MOPS/Platts) vs harga beli aktual

Referensi: TECH_SPEC_vessel_bunker_management.md
    """,
    'author': 'Sunartha ERP Consulting',
    'website': 'https://www.sunartha.co.id',
    'license': 'LGPL-3',
    'depends': [
        'fleet',
        'mail',
        'purchase',
        'stock',
        'account',
        # Hard dependency (beda pola dari vessel_voyage_pnl) — ROB reconciliation
        # (fitur inti) tidak bermakna tanpa data konsumsi & noon report, lihat
        # §7-§8 tech spec.
        'fleet_fuel_log',
        'vessel_chartering',
        'vessel_voyage_operations',
        'maritime',
    ],
    'data': [
        'security/vessel_bunker_management_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/vessel_bunker_price_reference_data.xml',
        'views/vessel_bunker_price_reference_views.xml',
        'views/res_config_settings_views.xml',
        'views/fleet_vehicle_views.xml',
        'views/vessel_bunker_management_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
