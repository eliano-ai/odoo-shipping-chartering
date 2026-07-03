# -*- coding: utf-8 -*-
{
    'name': 'Vessel Voyage Operations',
    'version': '19.0.1.0.0',
    'category': 'Fleet Management',
    'summary': 'Voyage lifecycle, port call, noon report, PDA/FDA, cargo document & delay log',
    'description': """
Vessel Voyage Operations — Layer 2 Komersial (#2)
====================================================
Menjembatani kontrak charter (vessel_chartering) dengan realita operasional
harian kapal di laut/pelabuhan — sumber data utama untuk modul finansial
berikutnya (vessel_voyage_pnl, vessel_bunker_management).

Fitur MVP (lihat TECH_SPEC_vessel_voyage_operations.md untuk detail lengkap):
- Voyage lifecycle: draft -> fixed -> sailing -> at_port -> completed
- Port rotation multi-port dengan ETA/ETB/ETD vs ATA/ATB/ATD
- Noon report / daily position report + approval workflow
- Port call management: agen, PDA/FDA variance, clearance checklist
- Cargo document tracking (B/L, manifest, mate's receipt)
- Delay & event log per voyage
- Dashboard posisi armada (OWL/Leaflet)
- Portal input untuk Nakhoda (noon report)

Referensi: TECH_SPEC_vessel_voyage_operations.md
    """,
    'author': 'Sunartha ERP Consulting',
    'website': 'https://www.sunartha.co.id',
    'license': 'LGPL-3',
    'depends': [
        'fleet',
        'mail',
        'portal',
        'vessel_chartering',
    ],
    'data': [
        'security/vessel_voyage_operations_groups.xml',
        'security/ir.model.access.csv',
        'security/vessel_voyage_operations_record_rules.xml',
        'data/ir_sequence_data.xml',
        'data/vessel_delay_type_data.xml',
        'data/vessel_clearance_document_type_data.xml',
        'data/vessel_disbursement_item_type_data.xml',
        'views/vessel_delay_type_views.xml',
        'views/vessel_clearance_document_type_views.xml',
        'views/vessel_disbursement_item_type_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        'wizards/vessel_voyage_cancel_wizard_views.xml',
        'views/vessel_voyage_views.xml',
        'views/vessel_charter_contract_views.xml',
        'views/vessel_port_call_views.xml',
        'views/vessel_noon_report_views.xml',
        'views/vessel_port_disbursement_views.xml',
        'views/vessel_cargo_document_views.xml',
        'views/vessel_voyage_delay_views.xml',
        'views/vessel_dashboard_map_actions.xml',
        'views/vessel_voyage_operations_menus.xml',
        'data/vessel_voyage_operations_mail_template_data.xml',
        'data/vessel_voyage_operations_cron_data.xml',
        'data/vessel_voyage_operations_demo.xml',
        'data/vessel_voyage_operations_voyage_demo.xml',
        'data/vessel_voyage_operations_port_call_demo.xml',
        'data/vessel_voyage_operations_noon_report_demo.xml',
        'data/vessel_voyage_operations_disbursement_demo.xml',
        'data/vessel_voyage_operations_cargo_document_demo.xml',
        'data/vessel_voyage_operations_delay_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Leaflet di-vendor sebagai static asset lokal (bukan CDN) — konsisten
            # dengan environment Docker self-hosted. Tile map tetap fetch dari
            # OpenStreetMap public tile server saat runtime browser (bukan dependency
            # server Odoo, dan self-hosting tile data dunia di luar scope MVP).
            'vessel_voyage_operations/static/lib/leaflet/leaflet.css',
            'vessel_voyage_operations/static/lib/leaflet/leaflet.js',
            'vessel_voyage_operations/static/src/scss/dashboard_map.scss',
            'vessel_voyage_operations/static/src/js/dashboard_map.js',
            'vessel_voyage_operations/static/src/xml/dashboard_map.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
