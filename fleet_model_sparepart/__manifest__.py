# -*- coding: utf-8 -*-
{
    'name': 'Fleet Model Sparepart',
    'version': '19.0.1.0.0',
    'category': 'Fleet',
    'summary': 'Master sparepart kapal dengan lookup Inventory (category: Vessel Inventory)',
    'description': """
Fleet Model Sparepart
======================
Fitur:
- Tab baru "Sparepart" di form fleet.vehicle.model
- Daftar kendaraan/kapal (fleet.vehicle) yang menggunakan model tersebut
- Tiap vehicle memiliki sub-list sparepart (fleet.model.sparepart):
    - Lookup ke product.product difilter by category "Vessel Inventory"
    - Auto-populate: part number, vendor, harga dari standard_price
    - Qty on-hand real-time dari stock.quant
    - Qty allocated: jumlah yang dialokasikan ke kapal ini (input manual)
- Data product category "Vessel Inventory" di-seed otomatis
- Model baru: fleet.model.sparepart
- Akses: Fleet Manager (full), Fleet User (read)
    """,
    'author': 'Custom Development',
    'depends': ['fleet', 'stock'],
    'data': [
        'security/fleet_model_sparepart_security.xml',
        'security/ir.model.access.csv', 
        'data/ir_sequence_data.xml',
        'data/vessel_inventory_category_data.xml',
        'views/fleet_model_sparepart_views.xml',
        'views/fleet_vehicle_model_views.xml',
        'views/fleet_model_sparepart_menu.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
