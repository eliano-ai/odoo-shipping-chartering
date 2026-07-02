# -*- coding: utf-8 -*-
import logging
import time

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ShopifyOrderSync(models.AbstractModel):
    _name = 'shopify.order.sync'
    _description = 'Shopify Order Sync Engine'

    def process_shopify_order(self, config, order_data):
        """
        Main entry point: create a Sales Order in Odoo from a Shopify order dict.
        Implements idempotency — will skip if order already exists.
        """
        start = time.time()
        Log = self.env['shopify.sync.log']

        shopify_order_id = str(order_data.get('id', ''))
        shopify_order_name = order_data.get('name', '')  # e.g. #1001

        # ── Idempotency check ──────────────────────────────────────────────
        existing_mapping = self.env['shopify.order.mapping'].search([
            ('config_id', '=', config.id),
            ('shopify_order_id', '=', shopify_order_id),
        ], limit=1)

        if existing_mapping:
            _logger.info(
                'Order %s already exists (SO: %s) — skipping.',
                shopify_order_name,
                existing_mapping.sale_order_id.name if existing_mapping.sale_order_id else 'N/A'
            )
            Log.log_sync(
                config, 'order', 'pull', 'skipped',
                record_name=shopify_order_name,
                shopify_record_ref=shopify_order_id,
                error_msg='Order already synced — idempotency skip.'
            )
            return existing_mapping.sale_order_id

        try:
            # ── Resolve routing ────────────────────────────────────────────
            company, warehouse = self._resolve_routing(config, order_data)

            # ── Resolve customer ───────────────────────────────────────────
            customer_sync = self.env['shopify.customer.sync']
            shopify_customer = order_data.get('customer')
            partner = customer_sync.get_or_create_partner(config, shopify_customer, order_data)

            shipping_address_data = order_data.get('shippingAddress')
            shipping_partner = customer_sync.get_shipping_address(
                config, shipping_address_data, partner
            )

            billing_address_data = order_data.get('billingAddress')
            billing_partner = customer_sync.get_shipping_address(
                config, billing_address_data, partner
            ) if billing_address_data else partner

            # ── Resolve currency ───────────────────────────────────────────
            currency_code = order_data.get('currencyCode', 'HKD')
            currency = self.env['res.currency'].search(
                [('name', '=', currency_code)], limit=1
            )
            if not currency:
                raise Exception(_(
                    'Currency %s not found in Odoo. Please activate it first.'
                ) % currency_code)

            # ── Resolve pricelist ──────────────────────────────────────────
            pricelist = self._resolve_pricelist(config, currency_code)

            # ── Create Sales Order ─────────────────────────────────────────
            so_vals = {
                'company_id': company.id,
                'partner_id': partner.id,
                'partner_shipping_id': shipping_partner.id,
                'partner_invoice_id': billing_partner.id,
                'warehouse_id': warehouse.id,
                'currency_id': currency.id,
                'pricelist_id': pricelist.id if pricelist else False,
                'client_order_ref': shopify_order_name,
                'note': order_data.get('note', '') or '',
                'origin': f'Shopify {shopify_order_name}',
                # Payment info fields
                'shopify_order_id': shopify_order_id,
                'shopify_financial_status': order_data.get('financialStatus', ''),
                'shopify_payment_gateway': self._extract_payment_gateway(order_data),
                'shopify_amount_paid': float(order_data.get('totalPrice', 0) or 0),
            }

            sale_order = self.env['sale.order'].with_company(company).create(so_vals)

            # ── Create order lines ─────────────────────────────────────────
            self._create_order_lines(config, sale_order, order_data)

            # ── Handle order-level discount ────────────────────────────────
            self._handle_order_discount(config, sale_order, order_data)

            # ── Add shipping line ──────────────────────────────────────────
            self._add_shipping_line(config, sale_order, order_data)

            # ── Confirm SO if configured ───────────────────────────────────
            if config.so_auto_confirm:
                sale_order.action_confirm()

            # ── Save order mapping ─────────────────────────────────────────
            self.env['shopify.order.mapping'].create({
                'config_id': config.id,
                'shopify_order_id': shopify_order_id,
                'shopify_order_name': shopify_order_name,
                'sale_order_id': sale_order.id,
                'sync_status': 'synced',
                'last_synced': fields.Datetime.now(),
                'shopify_financial_status': order_data.get('financialStatus', ''),
                'shopify_fulfillment_status': order_data.get('fulfillmentStatus', ''),
            })

            duration = int((time.time() - start) * 1000)
            Log.log_sync(
                config, 'order', 'pull', 'success',
                record_name=shopify_order_name,
                odoo_ref=sale_order.name,
                shopify_record_ref=shopify_order_id,
                duration_ms=duration
            )

            return sale_order

        except Exception as e:
            duration = int((time.time() - start) * 1000)
            Log.log_sync(
                config, 'order', 'pull', 'failed',
                record_name=shopify_order_name,
                shopify_record_ref=shopify_order_id,
                error_msg=str(e),
                duration_ms=duration
            )
            _logger.error('Failed to process Shopify order %s: %s', shopify_order_name, str(e))
            raise

    # ── Routing ────────────────────────────────────────────────────────────
    def _resolve_routing(self, config, order_data):
        """
        Determine which Odoo company and warehouse to use for this order.
        Logic: Malaysia shipping country → Malaysia company/warehouse.
        All others → default company/warehouse from config.
        """
        shipping_address = order_data.get('shippingAddress', {}) or {}
        country_code = shipping_address.get('countryCode', '').upper()

        if country_code == 'MY':
            # Try to find Malaysia company
            malaysia_company = self.env['res.company'].search([
                ('name', 'ilike', 'Malaysia'),
            ], limit=1)
            if malaysia_company:
                malaysia_warehouse = self.env['stock.warehouse'].search([
                    ('company_id', '=', malaysia_company.id),
                ], limit=1)
                if malaysia_warehouse:
                    return malaysia_company, malaysia_warehouse

        # Default: use config's company and warehouse
        return config.company_id, config.default_warehouse_id

    # ── Order lines ────────────────────────────────────────────────────────
    def _create_order_lines(self, config, sale_order, order_data):
        """Create SO lines from Shopify line items."""
        line_items = order_data.get('lineItems', {}).get('edges', [])
        for edge in line_items:
            line = edge.get('node', {})
            self._create_single_order_line(config, sale_order, line)

    def _create_single_order_line(self, config, sale_order, line_item):
        """Create a single SO line from a Shopify line item."""
        variant_id = line_item.get('variant', {}).get('id', '') if line_item.get('variant') else ''
        sku = line_item.get('sku', '') or ''

        # Lookup product from mapping
        product = None
        if variant_id:
            mapping = self.env['shopify.product.mapping'].search([
                ('config_id', '=', config.id),
                ('shopify_variant_id', '=', variant_id),
            ], limit=1)
            if mapping:
                product = mapping.product_id

        if not product and sku:
            # Fallback: search by SKU
            product = self.env['product.product'].search([
                ('default_code', '=', sku),
            ], limit=1)

        if not product:
            if config.missing_sku_mode == 'strict':
                raise Exception(_(
                    'Product with SKU "%s" (Shopify variant ID: %s) not found in Odoo. '
                    'Order processing halted (strict mode).'
                ) % (sku, variant_id))
            else:
                # Lenient mode: log warning and skip this line
                _logger.warning(
                    'Product SKU "%s" not found in Odoo — skipping line (lenient mode).',
                    sku
                )
                self.env['shopify.sync.log'].log_sync(
                    config, 'order', 'pull', 'needs_review',
                    record_name=f'Missing SKU: {sku}',
                    error_msg=f'SKU {sku} not found — line skipped (lenient mode).'
                )
                return

        # Resolve tax
        taxes = self._resolve_taxes(config, line_item)

        # Price from Shopify (already includes any variant-level discount)
        unit_price = float(line_item.get('originalUnitPriceSet', {}).get(
            'shopMoney', {}).get('amount', 0) or 0)
        discount_pct = self._calculate_line_discount(line_item)

        self.env['sale.order.line'].create({
            'order_id': sale_order.id,
            'product_id': product.id,
            'product_uom_qty': float(line_item.get('quantity', 1)),
            'price_unit': unit_price,
            'discount': discount_pct,
            'tax_id': [(6, 0, taxes.ids)] if taxes else [(5, 0, 0)],
            'name': line_item.get('title', product.name),
        })

    def _calculate_line_discount(self, line_item):
        """Calculate discount percentage from Shopify line item discount allocations."""
        original = float(
            line_item.get('originalUnitPriceSet', {}).get('shopMoney', {}).get('amount', 0) or 0
        )
        if not original:
            return 0.0
        discounted = float(
            line_item.get('discountedUnitPriceSet', {}).get('shopMoney', {}).get('amount', original) or original
        )
        if original > 0:
            return round((1 - discounted / original) * 100, 2)
        return 0.0

    def _resolve_taxes(self, config, line_item):
        """Map Shopify tax lines to Odoo taxes."""
        shopify_taxes = line_item.get('taxLines', [])
        odoo_taxes = self.env['account.tax']

        for shopify_tax in shopify_taxes:
            title = shopify_tax.get('title', '')
            tax_mapping = self.env['shopify.tax.mapping'].search([
                ('config_id', '=', config.id),
                ('shopify_tax_title', '=', title),
            ], limit=1)
            if tax_mapping:
                odoo_taxes |= tax_mapping.tax_id

        return odoo_taxes

    # ── Order-level discount ───────────────────────────────────────────────
    def _handle_order_discount(self, config, sale_order, order_data):
        """
        Handle order-level discounts (cart discounts in Shopify).
        Creates a negative SO line using the configured discount product.
        """
        discount_applications = order_data.get('discountApplications', {}).get('edges', [])
        if not discount_applications:
            return

        total_discount = float(
            order_data.get('totalDiscountsSet', {}).get('shopMoney', {}).get('amount', 0) or 0
        )
        if total_discount <= 0:
            return

        discount_product = config.default_discount_product_id
        if not discount_product:
            _logger.warning(
                'Order %s has discount %.2f but no discount product configured for store %s.',
                sale_order.client_order_ref, total_discount, config.name
            )
            return

        self.env['sale.order.line'].create({
            'order_id': sale_order.id,
            'product_id': discount_product.id,
            'product_uom_qty': 1,
            'price_unit': -total_discount,
            'name': 'Order Discount',
            'tax_id': [(5, 0, 0)],
        })

    # ── Shipping line ──────────────────────────────────────────────────────
    def _add_shipping_line(self, config, sale_order, order_data):
        """Add shipping cost as a SO line."""
        shipping_lines = order_data.get('shippingLines', {}).get('edges', [])
        if not shipping_lines:
            return

        shipping_product = config.default_shipping_product_id
        if not shipping_product:
            _logger.warning(
                'Order %s has shipping but no shipping product configured for store %s.',
                sale_order.client_order_ref, config.name
            )
            return

        total_shipping = float(
            order_data.get('totalShippingPriceSet', {}).get('shopMoney', {}).get('amount', 0) or 0
        )
        if total_shipping <= 0:
            return

        carrier_title = shipping_lines[0].get('node', {}).get('title', 'Shipping')

        self.env['sale.order.line'].create({
            'order_id': sale_order.id,
            'product_id': shipping_product.id,
            'product_uom_qty': 1,
            'price_unit': total_shipping,
            'name': carrier_title,
            'tax_id': [(5, 0, 0)],
        })

    # ── Payment info ───────────────────────────────────────────────────────
    def _extract_payment_gateway(self, order_data):
        """Extract payment gateway name from order data."""
        try:
            transactions = order_data.get('transactions', {}).get('edges', [])
            if transactions:
                gateway = transactions[0].get('node', {}).get('gateway', '')
                return gateway
        except (KeyError, IndexError, TypeError):
            pass
        return ''

    def _resolve_pricelist(self, config, currency_code):
        """Find pricelist for a given currency code."""
        pl_mapping = self.env['shopify.pricelist.mapping'].search([
            ('config_id', '=', config.id),
            ('shopify_currency', '=', currency_code),
        ], limit=1)
        if pl_mapping:
            return pl_mapping.pricelist_id
        return config.default_pricelist_id

    # ── Polling fallback ───────────────────────────────────────────────────
    def poll_new_orders(self, config):
        """
        Pull new/updated orders from Shopify since last_order_sync.
        Used as fallback when webhooks may have been missed.
        """
        client = self.env['shopify.api.client']

        # Use Shopify timestamp (not local) to avoid timezone issues
        cursor_time = config.last_order_sync
        updated_at_min = cursor_time.strftime('%Y-%m-%dT%H:%M:%S') if cursor_time else None

        query = """
        query getOrders($cursor: String, $query: String) {
          orders(first: 50, after: $cursor, query: $query, sortKey: UPDATED_AT) {
            edges {
              node {
                id
                name
                createdAt
                updatedAt
                financialStatus
                fulfillmentStatus
                currencyCode
                note
                totalPrice
                totalDiscountsSet { shopMoney { amount } }
                totalShippingPriceSet { shopMoney { amount } }
                customer {
                  id email firstName lastName phone
                  defaultAddress { address1 address2 city zip countryCode provinceCode }
                }
                shippingAddress { address1 address2 city zip countryCode provinceCode firstName lastName phone }
                billingAddress { address1 address2 city zip countryCode provinceCode firstName lastName phone }
                lineItems(first: 50) {
                  edges {
                    node {
                      title sku quantity
                      originalUnitPriceSet { shopMoney { amount } }
                      discountedUnitPriceSet { shopMoney { amount } }
                      taxLines { title rate priceSet { shopMoney { amount } } }
                      variant { id sku }
                    }
                  }
                }
                shippingLines(first: 5) {
                  edges { node { title originalPriceSet { shopMoney { amount } } } }
                }
                discountApplications(first: 5) {
                  edges { node { allocationMethod targetType value { ... on PricingPercentageValue { percentage } ... on MoneyV2 { amount } } } }
                }
                transactions(first: 3) {
                  edges { node { gateway status } }
                }
              }
            }
            pageInfo { hasNextPage endCursor }
          }
        }
        """

        query_str = ''
        if updated_at_min:
            query_str = f'updated_at:>={updated_at_min}'

        variables = {'cursor': None, 'query': query_str}
        processed = 0
        latest_updated_at = None

        # Manual pagination
        while True:
            result = client.graphql_query(config, query, variables)
            orders_data = result.get('data', {}).get('orders', {})
            edges = orders_data.get('edges', [])
            page_info = orders_data.get('pageInfo', {})

            for edge in edges:
                order_node = edge.get('node', {})
                try:
                    self.process_shopify_order(config, order_node)
                    processed += 1
                    updated_at = order_node.get('updatedAt')
                    if updated_at:
                        latest_updated_at = updated_at
                except Exception as e:
                    _logger.error(
                        'Polling: failed to process order %s: %s',
                        order_node.get('name', ''), str(e)
                    )

            if not page_info.get('hasNextPage'):
                break
            variables['cursor'] = page_info.get('endCursor')

        # Update polling cursor
        if latest_updated_at:
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(latest_updated_at.replace('Z', '+00:00'))
                config.write({'last_order_sync': fields.Datetime.to_string(dt)})
            except Exception:
                pass

        _logger.info(
            'Order polling done for store %s: %d orders processed.',
            config.name, processed
        )
