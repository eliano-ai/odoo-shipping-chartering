# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SHOPIFY_API_VERSION = '2026-01'


class ShopifyConfig(models.Model):
    _name = 'shopify.config'
    _description = 'Shopify Store Configuration'
    _rec_name = 'name'

    # ── Basic Info ─────────────────────────────────────────────────────────
    name = fields.Char(
        string='Configuration Name',
        required=True,
        help='Descriptive name, e.g. "Nustik HK Store - Production"'
    )
    shop_url = fields.Char(
        string='Shop URL',
        required=True,
        help='Format: storename.myshopify.com (without https://)'
    )
    api_version = fields.Char(
        string='Shopify API Version',
        default=SHOPIFY_API_VERSION,
        required=True,
        help='Shopify API version to use, e.g. 2026-01'
    )
    is_active = fields.Boolean(string='Active', default=True)

    # ── Credentials (stored encrypted via password=True) ───────────────────
    access_token = fields.Char(
        string='Access Token',
        password=True,
        required=True,
        help='Access token from Shopify Custom App. Shown only once — store securely.'
    )
    webhook_secret = fields.Char(
        string='Webhook Secret',
        password=True,
        required=True,
        help='Used to verify HMAC signature of incoming webhooks.'
    )

    # ── Odoo Links ─────────────────────────────────────────────────────────
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help='Default Odoo company for this store.'
    )
    default_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Default Warehouse',
        required=True,
        help='Default warehouse for order routing if no specific mapping matches.'
    )
    default_pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Default Pricelist',
        help='Default pricelist used when no market-specific pricelist mapping is found.'
    )

    # ── Sync Toggles ───────────────────────────────────────────────────────
    sync_product = fields.Boolean(string='Sync Products', default=True)
    sync_inventory = fields.Boolean(string='Sync Inventory', default=True)
    sync_order = fields.Boolean(string='Sync Orders', default=True)

    # ── Order Behavior ─────────────────────────────────────────────────────
    so_auto_confirm = fields.Boolean(
        string='Auto-Confirm Sales Orders',
        default=False,
        help='If enabled, Sales Orders from Shopify are automatically confirmed.'
    )
    missing_sku_mode = fields.Selection(
        [('lenient', 'Lenient — skip missing lines, order still created'),
         ('strict', 'Strict — halt order, alert admin')],
        string='Missing SKU Behavior',
        default='lenient',
        required=True,
        help='What to do when a Shopify order line SKU is not found in Odoo.'
    )
    default_shipping_product_id = fields.Many2one(
        'product.product',
        string='Shipping Line Product',
        domain=[('type', '=', 'service')],
        help='Service product used to represent shipping cost on Sales Orders.'
    )
    default_discount_product_id = fields.Many2one(
        'product.product',
        string='Discount Line Product',
        domain=[('type', '=', 'service')],
        help='Service product used for order-level discounts (negative SO line).'
    )
    default_guest_partner_id = fields.Many2one(
        'res.partner',
        string='Guest Customer Contact',
        help='Fallback Contact used when a Shopify order has no customer email.'
    )

    # ── Sync Timestamps (polling cursors) ──────────────────────────────────
    last_order_sync = fields.Datetime(
        string='Last Order Sync',
        help='Timestamp of last successful order poll. Used as cursor for polling fallback.'
    )
    last_inventory_sync = fields.Datetime(
        string='Last Inventory Sync'
    )
    last_product_sync = fields.Datetime(
        string='Last Product Sync'
    )

    # ── Mapping sub-records (computed counts for display) ──────────────────
    location_mapping_ids = fields.One2many(
        'shopify.location.mapping', 'config_id', string='Location Mappings'
    )
    tax_mapping_ids = fields.One2many(
        'shopify.tax.mapping', 'config_id', string='Tax Mappings'
    )
    pricelist_mapping_ids = fields.One2many(
        'shopify.pricelist.mapping', 'config_id', string='Pricelist Mappings'
    )

    location_mapping_count = fields.Integer(
        compute='_compute_mapping_counts'
    )
    tax_mapping_count = fields.Integer(
        compute='_compute_mapping_counts'
    )
    pricelist_mapping_count = fields.Integer(
        compute='_compute_mapping_counts'
    )

    @api.depends('location_mapping_ids', 'tax_mapping_ids', 'pricelist_mapping_ids')
    def _compute_mapping_counts(self):
        for rec in self:
            rec.location_mapping_count = len(rec.location_mapping_ids)
            rec.tax_mapping_count = len(rec.tax_mapping_ids)
            rec.pricelist_mapping_count = len(rec.pricelist_mapping_ids)

    # ── API Base URL ────────────────────────────────────────────────────────
    def _get_api_base_url(self):
        self.ensure_one()
        shop = self.shop_url.strip().rstrip('/')
        if not shop.endswith('.myshopify.com'):
            shop = shop + '.myshopify.com'
        return f"https://{shop}/admin/api/{self.api_version}"

    def _get_graphql_url(self):
        self.ensure_one()
        return f"{self._get_api_base_url()}/graphql.json"

    # ── Actions ────────────────────────────────────────────────────────────
    def action_test_connection(self):
        """Test connection to Shopify API by fetching shop info."""
        self.ensure_one()
        client = self.env['shopify.api.client']
        try:
            query = """
            {
              shop {
                name
                email
                primaryDomain { url }
              }
            }
            """
            result = client.graphql_query(self, query)
            shop_data = result.get('data', {}).get('shop', {})
            if shop_data:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Successful'),
                        'message': _(
                            'Connected to: %(name)s (%(email)s)',
                            name=shop_data.get('name', ''),
                            email=shop_data.get('email', '')
                        ),
                        'type': 'success',
                    }
                }
        except Exception as e:
            raise UserError(_('Connection failed: %s') % str(e))

    def action_register_webhooks(self):
        """Register all required webhooks to Shopify."""
        self.ensure_one()
        webhook_model = self.env['shopify.webhook.manager']
        webhook_model.register_all_webhooks(self)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Webhooks Registered'),
                'message': _('All webhooks have been registered to Shopify.'),
                'type': 'success',
            }
        }

    def action_open_bulk_sync_wizard(self):
        """Open bulk sync wizard."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bulk Sync'),
            'res_model': 'shopify.bulk.sync.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_config_id': self.id},
        }
