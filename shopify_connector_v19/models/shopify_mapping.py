# -*- coding: utf-8 -*-
from odoo import models, fields


class ShopifyLocationMapping(models.Model):
    _name = 'shopify.location.mapping'
    _description = 'Shopify Location ↔ Odoo Warehouse Mapping'
    _rec_name = 'shopify_location_name'

    config_id = fields.Many2one('shopify.config', string='Store Config', required=True, ondelete='cascade')
    warehouse_id = fields.Many2one('stock.warehouse', string='Odoo Warehouse', required=True)
    shopify_location_id = fields.Char(string='Shopify Location ID', required=True)
    shopify_location_name = fields.Char(string='Shopify Location Name')
    is_primary = fields.Boolean(string='Primary Location', default=False)

    _sql_constraints = [
        ('unique_warehouse_per_config', 'UNIQUE(config_id, warehouse_id)',
         'Each warehouse can only be mapped once per store.'),
        ('unique_location_per_config', 'UNIQUE(config_id, shopify_location_id)',
         'Each Shopify location can only be mapped once per store.'),
    ]


class ShopifyProductMapping(models.Model):
    _name = 'shopify.product.mapping'
    _description = 'Shopify Variant ↔ Odoo Product Variant Mapping'
    _rec_name = 'sku'

    config_id = fields.Many2one('shopify.config', string='Store Config', required=True, ondelete='cascade')
    product_id = fields.Many2one(
        'product.product', string='Odoo Product Variant',
        required=True, ondelete='cascade'
    )
    shopify_product_id = fields.Char(string='Shopify Product ID')
    shopify_variant_id = fields.Char(string='Shopify Variant ID')
    shopify_inventory_item_id = fields.Char(
        string='Shopify Inventory Item ID',
        help='Separate from variant ID — required for inventory level updates.'
    )
    sku = fields.Char(string='SKU', help='Primary key for matching between systems.')
    last_synced = fields.Datetime(string='Last Synced')
    sync_status = fields.Selection(
        [('synced', 'Synced'), ('pending', 'Pending'), ('error', 'Error')],
        string='Sync Status', default='pending'
    )

    _sql_constraints = [
        ('unique_product_per_config', 'UNIQUE(config_id, product_id)',
         'Each product variant can only be mapped once per store.'),
        ('unique_shopify_variant_per_config', 'UNIQUE(config_id, shopify_variant_id)',
         'Each Shopify variant can only be mapped once per store.'),
    ]


class ShopifyOrderMapping(models.Model):
    _name = 'shopify.order.mapping'
    _description = 'Shopify Order ↔ Odoo Sales Order Mapping'
    _rec_name = 'shopify_order_name'

    config_id = fields.Many2one('shopify.config', string='Store Config', required=True, ondelete='cascade')
    shopify_order_id = fields.Char(string='Shopify Order ID', required=True)
    shopify_order_name = fields.Char(string='Shopify Order Name', help='e.g. #1001')
    sale_order_id = fields.Many2one('sale.order', string='Sales Order', ondelete='set null')
    sync_status = fields.Selection(
        [('synced', 'Synced'), ('pending', 'Pending'), ('error', 'Error'), ('needs_review', 'Needs Review')],
        string='Sync Status', default='pending'
    )
    last_synced = fields.Datetime(string='Last Synced')
    shopify_financial_status = fields.Char(string='Financial Status')
    shopify_fulfillment_status = fields.Char(string='Fulfillment Status')

    _sql_constraints = [
        ('unique_shopify_order_per_config', 'UNIQUE(config_id, shopify_order_id)',
         'Each Shopify order can only be mapped once per store.'),
    ]


class ShopifyCustomerMapping(models.Model):
    _name = 'shopify.customer.mapping'
    _description = 'Shopify Customer ↔ Odoo Contact Mapping'
    _rec_name = 'email'

    config_id = fields.Many2one('shopify.config', string='Store Config', required=True, ondelete='cascade')
    shopify_customer_id = fields.Char(string='Shopify Customer ID', required=True)
    partner_id = fields.Many2one('res.partner', string='Odoo Contact', ondelete='set null')
    email = fields.Char(string='Email', help='Primary identifier for customer matching.')

    _sql_constraints = [
        ('unique_shopify_customer_per_config', 'UNIQUE(config_id, shopify_customer_id)',
         'Each Shopify customer can only be mapped once per store.'),
    ]


class ShopifyTaxMapping(models.Model):
    _name = 'shopify.tax.mapping'
    _description = 'Shopify Tax ↔ Odoo Tax Mapping'
    _rec_name = 'shopify_tax_title'

    config_id = fields.Many2one('shopify.config', string='Store Config', required=True, ondelete='cascade')
    shopify_tax_title = fields.Char(string='Shopify Tax Title', required=True, help='e.g. "SST", "VAT"')
    shopify_tax_rate = fields.Float(string='Shopify Tax Rate', help='e.g. 0.06 for 6%')
    tax_id = fields.Many2one('account.tax', string='Odoo Tax', required=True)

    _sql_constraints = [
        ('unique_tax_title_per_config', 'UNIQUE(config_id, shopify_tax_title)',
         'Each tax title can only be mapped once per store.'),
    ]


class ShopifyPricelistMapping(models.Model):
    _name = 'shopify.pricelist.mapping'
    _description = 'Shopify Market/Currency ↔ Odoo Pricelist Mapping'
    _rec_name = 'shopify_currency'

    config_id = fields.Many2one('shopify.config', string='Store Config', required=True, ondelete='cascade')
    pricelist_id = fields.Many2one('product.pricelist', string='Odoo Pricelist', required=True)
    shopify_currency = fields.Char(
        string='Shopify Currency Code', required=True,
        help='ISO currency code, e.g. HKD, USD, MYR'
    )
    shopify_market_id = fields.Char(
        string='Shopify Market ID',
        help='Optional — for market-specific price sync.'
    )

    _sql_constraints = [
        ('unique_currency_per_config', 'UNIQUE(config_id, shopify_currency)',
         'Each currency can only be mapped once per store.'),
    ]
