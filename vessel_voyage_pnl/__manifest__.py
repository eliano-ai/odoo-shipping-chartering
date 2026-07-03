# -*- coding: utf-8 -*-
{
    'name': 'Vessel Voyage P&L',
    'version': '19.0.1.0.0',
    'category': 'Fleet Management',
    'summary': 'Voyage P&L, alokasi biaya, vessel P&L bulanan, budget & dashboard direksi',
    'description': """
Vessel Voyage P&L — Layer 3 Finansial (#3)
====================================================
Payoff dari Analytic Plans (Vessel + Voyage) yang sudah dikunci sejak
vessel_chartering — mengagregasi revenue, direct cost, dan biaya tidak
langsung (crew, maintenance, depresiasi, overhead) menjadi P&L per voyage,
per kapal per periode, lengkap dengan variance terhadap estimate dan budget.

Fitur MVP (lihat TECH_SPEC_vessel_voyage_pnl.md untuk detail lengkap):
- Voyage P&L statement (revenue, direct cost, allocated cost)
- Metode alokasi biaya tidak langsung configurable per kategori
- Estimate vs Actual — variance analysis per komponen
- Vessel P&L bulanan (agregasi lintas-voyage per kapal, termasuk idle cost)
- Budget per kapal per tahun + variance terhadap actual
- Dashboard direksi (utilisasi, TCE trend, top voyage rugi, demurrage outstanding)

Referensi: TECH_SPEC_vessel_voyage_pnl.md
    """,
    'author': 'Sunartha ERP Consulting',
    'website': 'https://www.sunartha.co.id',
    'license': 'LGPL-3',
    'depends': [
        'fleet',
        'mail',
        'account',
        'vessel_chartering',
        'vessel_voyage_operations',
        'maritime',
    ],
    'data': [
        'security/vessel_voyage_pnl_groups.xml',
        'security/ir.model.access.csv',
        'data/vessel_pnl_cost_category_data.xml',
        'data/vessel_cost_allocation_rule_data.xml',
        'views/vessel_pnl_cost_category_views.xml',
        'views/vessel_cost_allocation_rule_views.xml',
        'views/res_config_settings_views.xml',
        'views/fleet_vehicle_views.xml',
        'views/vessel_voyage_pnl_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
