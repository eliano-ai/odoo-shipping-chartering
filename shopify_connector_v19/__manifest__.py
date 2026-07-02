# -*- coding: utf-8 -*-
{
    'name': 'Shopify Connector',
    'version': '19.0.1.0.0',
    'category': 'Sales/eCommerce',
    'summary': 'Integrate Shopify with Odoo — sync products, inventory, orders, customers, and tracking.',
    'description': """
Shopify Connector
=================
Bidirectional integration between Shopify and Odoo 19.

Features:
- Product & variant sync (Odoo → Shopify)
- Inventory sync per warehouse/location (Odoo → Shopify)
- Order import (Shopify → Odoo Sales Order)
- Customer sync (Shopify → Odoo Contact)
- Tracking number sync (Odoo → Shopify)
- Refund & cancellation handling
- Webhook-based real-time sync with polling fallback
- Multi-company & multi-store support
- Dashboard monitoring & logging

Shopify API Version: 2026-01
Developed by: PT Sun Artha Putra Mandiri (Sunartha)
    """,
    'author': 'PT Sun Artha Putra Mandiri (Sunartha)',
    'website': 'https://sunartha.co.id',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale_management',
        'stock',
        'account',
        'delivery',
        'queue_job',
    ],
    'data': [
        'security/res_groups.xml',          
        'security/ir.model.access.csv',  
        'data/scheduled_actions.xml',
        'views/shopify_config_views.xml',
        'views/shopify_log_views.xml',
        'views/shopify_dashboard_views.xml',
        'views/sale_order_views.xml',
        'wizard/bulk_sync_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {},
    'installable': True,
    'application': False,
    'auto_install': False,
}
