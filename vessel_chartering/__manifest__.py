# -*- coding: utf-8 -*-
{
    'name': 'Vessel Chartering',
    'version': '19.0.1.0.0',
    'category': 'Fleet Management',
    'summary': 'Charter party management — Voyage Charter, Time Charter, COA, laytime & demurrage',
    'description': """
Vessel Chartering — Layer 2 Komersial
=======================================
Modul komersial yang menjembatani kontrak charter kapal ke sale/purchase/account
standar Odoo. Menjadi entry point revenue engine perusahaan pelayaran (charter-out)
dan cost engine (charter-in).

Fitur MVP (lihat TECH_SPEC_vessel_chartering.md untuk detail lengkap):
- Charter Party management: Voyage Charter, Time Charter, COA
- Charter-Out (revenue) & Charter-In (cost) dalam satu model
- Freight per MT dengan laytime & demurrage/despatch calculator
- Hire statement untuk Time Charter (on-hire/off-hire)
- Voyage estimate (pre-fixture) dengan kalkulasi bunker & TCE
- Dual Analytic Plans (Vessel + Voyage/Contract), Odoo 19 multi-plan
- Invoicing otomatis ke account.move

Referensi: TECH_SPEC_vessel_chartering.md
    """,
    'author': 'Sunartha ERP Consulting',
    'website': 'https://www.sunartha.co.id',
    'license': 'LGPL-3',
    'depends': [
        'fleet',
        'fleet_document_id',
        'account',
        'analytic',
        'mail',
    ],
    'data': [
        'security/vessel_chartering_security.xml',
        'security/ir.model.access.csv',
        'data/vessel_chartering_analytic_plan_data.xml',
        'data/vessel_laytime_interruption_type_data.xml',
        'data/vessel_charter_contract_sequence_data.xml',
        'data/vessel_chartering_product_data.xml',
        'views/vessel_cargo_type_views.xml',
        'views/vessel_charter_terms_views.xml',
        'views/vessel_laytime_interruption_type_views.xml',
        'views/res_partner_port_views.xml',
        'views/vessel_charter_contract_views.xml',
        'views/vessel_voyage_estimate_views.xml',
        'views/vessel_laytime_calculation_views.xml',
        'views/vessel_hire_statement_line_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/vessel_charter_cancel_wizard_views.xml',
        'wizard/vessel_freight_invoice_wizard_views.xml',
        'views/fleet_vehicle_views.xml',
        'views/vessel_chartering_menus.xml',
        'views/vessel_laytime_calculation_menus.xml',
        'data/vessel_chartering_demo.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
