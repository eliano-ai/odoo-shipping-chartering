# -*- coding: utf-8 -*-
import base64
import hashlib
import logging
import time

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ShopifyProductSync(models.AbstractModel):
    _name = 'shopify.product.sync'
    _description = 'Shopify Product Sync Engine'

    # ── Public entry points ────────────────────────────────────────────────
    def sync_product_to_shopify(self, config, product_tmpl):
        """
        Sync a product.template and all its variants to Shopify.
        Creates or updates depending on existing mapping.
        """
        start = time.time()
        client = self.env['shopify.api.client']
        Log = self.env['shopify.sync.log']

        variants = product_tmpl.product_variant_ids.filtered(lambda v: v.default_code)
        if not variants:
            Log.log_sync(
                config, 'product', 'push', 'skipped',
                record_name=product_tmpl.name,
                error_msg='No variants with SKU found — skipping.'
            )
            return

        # Check if any variant already has a mapping
        existing_mapping = self.env['shopify.product.mapping'].search([
            ('config_id', '=', config.id),
            ('product_id', 'in', variants.ids),
        ], limit=1)

        try:
            if existing_mapping:
                shopify_product_id = existing_mapping.shopify_product_id
                try:
                    self._update_product(config, client, product_tmpl, variants, shopify_product_id)
                except UserError as e:
                    if 'does not exist' in str(e).lower():
                        _logger.warning(
                            'Shopify product %s not found for "%s" — clearing stale mapping and recreating.',
                            shopify_product_id, product_tmpl.name
                        )
                        existing_mapping.unlink()
                        self._create_product(config, client, product_tmpl, variants)
                    else:
                        raise
            else:
                self._create_product(config, client, product_tmpl, variants)

            duration = int((time.time() - start) * 1000)
            Log.log_sync(
                config, 'product', 'push', 'success',
                record_name=product_tmpl.name,
                odoo_ref=str(product_tmpl.id),
                duration_ms=duration
            )

        except Exception as e:
            duration = int((time.time() - start) * 1000)
            Log.log_sync(
                config, 'product', 'push', 'failed',
                record_name=product_tmpl.name,
                odoo_ref=str(product_tmpl.id),
                error_msg=str(e),
                duration_ms=duration
            )
            _logger.error('Failed to sync product %s: %s', product_tmpl.name, str(e))

    def bulk_sync_products(self, config):
        """Sync all active, sellable products to Shopify."""
        products = self.env['product.template'].search([
            ('active', '=', True),
            ('sale_ok', '=', True),
            ('type', '!=', 'service'),
        ])
        _logger.info('Starting bulk product sync: %d products for store %s', len(products), config.name)
        for tmpl in products:
            self.sync_product_to_shopify(config, tmpl)

        self._archive_orphaned_shopify_products(config)

    def _archive_orphaned_shopify_products(self, config):
        """
        Set status=DRAFT in Shopify for products whose Odoo variant has been archived.
        Runs at the end of bulk_sync so stale products don't stay visible to customers.
        Mappings are kept intact so re-activating the product in Odoo triggers an update.
        """
        client = self.env['shopify.api.client']
        Log = self.env['shopify.sync.log']

        orphan_mappings = self.env['shopify.product.mapping'].with_context(active_test=False).search([
            ('config_id', '=', config.id),
            ('product_id.active', '=', False),
            ('shopify_product_id', '!=', False),
        ])
        if not orphan_mappings:
            return

        shopify_product_ids = set(orphan_mappings.mapped('shopify_product_id'))
        _logger.info(
            'Auto-archiving %d Shopify products for store %s',
            len(shopify_product_ids), config.name
        )

        mutation = """
        mutation productUpdate($input: ProductInput!) {
          productUpdate(input: $input) {
            product { id title }
            userErrors { field message }
          }
        }
        """
        for shopify_product_id in shopify_product_ids:
            try:
                result = client.graphql_query(config, mutation, {
                    'input': {'id': shopify_product_id, 'status': 'DRAFT'}
                })
                data = result.get('data', {}).get('productUpdate', {})
                user_errors = data.get('userErrors', [])
                product_title = (data.get('product') or {}).get('title', shopify_product_id)

                if user_errors:
                    Log.log_sync(
                        config, 'product', 'push', 'failed',
                        record_name=product_title,
                        shopify_record_ref=shopify_product_id,
                        error_msg=f'Auto-archive failed: {user_errors}',
                    )
                else:
                    Log.log_sync(
                        config, 'product', 'push', 'success',
                        record_name=product_title,
                        shopify_record_ref=shopify_product_id,
                        error_msg='Auto-archived: product inactive in Odoo',
                    )
            except Exception as e:
                _logger.warning('Failed to archive Shopify product %s: %s', shopify_product_id, str(e))
                Log.log_sync(
                    config, 'product', 'push', 'failed',
                    shopify_record_ref=shopify_product_id,
                    error_msg=f'Auto-archive error: {str(e)}',
                )

    # ── Create product ─────────────────────────────────────────────────────
    def _create_product(self, config, client, product_tmpl, variants):
        """
        Create a new product in Shopify.

        NOTE: As of recent Shopify API versions (2024-04+), ProductInput no
        longer accepts `bodyHtml`, `options`, or `variants` directly.
        The flow is now split into three steps:
          1. productCreate — basic product fields only (no variants/options)
          2. productOptionsCreate — define option names/values (only if the
             product has attributes; skipped for simple single-variant products)
          3. productVariantsBulkCreate — create variants with SKU/price/etc,
             linked to the option values defined in step 2
        """
        options = self._build_options(product_tmpl)

        # ── Step 1: Create base product (no options, no variants) ──────────
        mutation = """
        mutation productCreate($input: ProductInput!) {
          productCreate(input: $input) {
            product {
              id
              variants(first: 1) {
                edges {
                  node {
                    id
                    sku
                    inventoryItem { id }
                  }
                }
              }
            }
            userErrors { field message }
          }
        }
        """
        variables = {
            'input': {
                'title': product_tmpl.name,
                'descriptionHtml': product_tmpl.description_sale or '',
                'productType': product_tmpl.categ_id.name if product_tmpl.categ_id else '',
                'tags': product_tmpl.mapped('product_tag_ids.name'),
                'status': 'ACTIVE' if product_tmpl.active else 'DRAFT',
            }
        }

        result = client.graphql_query(config, mutation, variables)
        data = result.get('data', {}).get('productCreate', {})

        user_errors = data.get('userErrors', [])
        if user_errors:
            raise UserError(_('Shopify product create errors: %s') % str(user_errors))

        shopify_product = data.get('product', {})
        shopify_product_id = shopify_product.get('id', '')

        if not shopify_product_id:
            raise UserError(_('Shopify did not return a product ID on create.'))

        # ── Step 2: Define options (only needed for multi-variant products) ─
        if options:
            self._create_product_options(config, client, shopify_product_id, options)

        # ── Step 3: Create variants with SKU, price, barcode, etc ──────────
        # A product always has at least a default variant — remove it after
        # the real ones are created (avoids a stray "Default Title" variant
        # for multi-variant products).
        default_variant_id = None
        first_variant_edges = shopify_product.get('variants', {}).get('edges', [])
        if first_variant_edges:
            default_variant_id = first_variant_edges[0].get('node', {}).get('id')

        created_variants = self._create_product_variants(
            config, client, shopify_product_id, variants, options, default_variant_id
        )

        # Save mappings using the variants returned from bulk create
        self._save_variant_mappings_from_bulk(config, variants, created_variants, shopify_product_id)

        # Sync images
        self._sync_product_images(config, client, product_tmpl, shopify_product_id)

        # Sync prices per pricelist
        self._sync_product_prices(config, client, variants, shopify_product_id)

    # ── Step 2 helper: create options ──────────────────────────────────────
    def _create_product_options(self, config, client, shopify_product_id, options):
        """Create product options (e.g. Size, Color) via productOptionsCreate."""
        mutation = """
        mutation productOptionsCreate($productId: ID!, $options: [OptionCreateInput!]!) {
          productOptionsCreate(productId: $productId, options: $options) {
            product { id }
            userErrors { field message }
          }
        }
        """
        option_input = [{
            'name': opt['name'],
            'values': [{'name': v} for v in opt['values']],
        } for opt in options]

        variables = {
            'productId': shopify_product_id,
            'options': option_input,
        }
        result = client.graphql_query(config, mutation, variables)
        data = result.get('data', {}).get('productOptionsCreate', {})
        user_errors = data.get('userErrors', [])
        if user_errors:
            raise UserError(_('Shopify product options create errors: %s') % str(user_errors))

    # ── Step 3 helper: bulk create variants ──────────────────────────────────
    def _create_product_variants(self, config, client, shopify_product_id,
                                  odoo_variants, options, default_variant_id=None):
        """
        Create variants via productVariantsBulkCreate.
        Returns list of created variant nodes (id, sku, inventoryItem.id).

        For simple products (no options), Shopify already created a "Default Title"
        variant on productCreate — update it instead of creating a duplicate.
        """
        if not options and default_variant_id:
            return self._update_default_variant(
                config, client, shopify_product_id, odoo_variants[0], default_variant_id
            )

        variants_input = []
        for variant in odoo_variants:
            option_values = []
            if options:
                for attr_value in variant.product_template_attribute_value_ids:
                    option_values.append({
                        'optionName': attr_value.attribute_id.name,
                        'name': attr_value.name,
                    })

            price = variant.lst_price

            variant_payload = {
                'price': str(price),
                'inventoryItem': {
                    'sku': variant.default_code or '',
                    'tracked': True,
                },
            }
            if variant.barcode:
                variant_payload['barcode'] = variant.barcode
            if option_values:
                variant_payload['optionValues'] = option_values

            variants_input.append(variant_payload)

        if not variants_input:
            return []

        mutation = """
        mutation productVariantsBulkCreate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
          productVariantsBulkCreate(productId: $productId, variants: $variants) {
            productVariants {
              id
              sku
              inventoryItem { id }
            }
            userErrors { field message }
          }
        }
        """
        variables = {
            'productId': shopify_product_id,
            'variants': variants_input,
        }
        result = client.graphql_query(config, mutation, variables)
        data = result.get('data', {}).get('productVariantsBulkCreate', {})
        user_errors = data.get('userErrors', [])
        if user_errors:
            raise UserError(_('Shopify variant create errors: %s') % str(user_errors))

        created_variants = data.get('productVariants', [])

        # Clean up the stray default variant Shopify auto-creates on productCreate
        if default_variant_id:
            self._delete_default_variant(config, client, shopify_product_id, default_variant_id, created_variants)

        return created_variants

    def _delete_default_variant(self, config, client, shopify_product_id, default_variant_id, created_variants):
        """Remove the auto-generated 'Default Title' variant after real variants are created."""
        # Safety: never delete if it's one of the variants we just created
        created_ids = {v.get('id') for v in created_variants}
        if default_variant_id in created_ids:
            return

        mutation = """
        mutation productVariantsBulkDelete($productId: ID!, $variantsIds: [ID!]!) {
          productVariantsBulkDelete(productId: $productId, variantsIds: $variantsIds) {
            userErrors { field message }
          }
        }
        """
        variables = {
            'productId': shopify_product_id,
            'variantsIds': [default_variant_id],
        }
        try:
            client.graphql_query(config, mutation, variables)
        except Exception as e:
            # Non-blocking — a leftover default variant is cosmetic, not fatal
            _logger.warning(
                'Could not remove default variant %s on product %s: %s',
                default_variant_id, shopify_product_id, str(e)
            )

    def _update_default_variant(self, config, client, shopify_product_id, odoo_variant, default_variant_id):
        """
        For simple (no-option) products: update the auto-created 'Default Title'
        variant with the Odoo variant's SKU, price, and barcode.
        Returns a list with one variant node to stay consistent with bulk create.
        """
        mutation = """
        mutation productVariantsBulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
          productVariantsBulkUpdate(productId: $productId, variants: $variants) {
            productVariants {
              id
              sku
              inventoryItem { id }
            }
            userErrors { field message }
          }
        }
        """
        variant_input = {
            'id': default_variant_id,
            'price': str(odoo_variant.lst_price),
            'inventoryItem': {
                'sku': odoo_variant.default_code or '',
                'tracked': True,
            },
        }
        if odoo_variant.barcode:
            variant_input['barcode'] = odoo_variant.barcode

        variables = {
            'productId': shopify_product_id,
            'variants': [variant_input],
        }
        result = client.graphql_query(config, mutation, variables)
        data = result.get('data', {}).get('productVariantsBulkUpdate', {})
        user_errors = data.get('userErrors', [])
        if user_errors:
            raise UserError(_('Shopify default variant update errors: %s') % str(user_errors))

        return data.get('productVariants', [])

    # ── Update product ─────────────────────────────────────────────────────
    def _update_product(self, config, client, product_tmpl, variants, shopify_product_id):
        """Update existing product in Shopify."""
        mutation = """
        mutation productUpdate($input: ProductInput!) {
          productUpdate(input: $input) {
            product { id }
            userErrors { field message }
          }
        }
        """
        variables = {
            'input': {
                'id': shopify_product_id,
                'title': product_tmpl.name,
                'descriptionHtml': product_tmpl.description_sale or '',
                'status': 'ACTIVE' if product_tmpl.active else 'DRAFT',
            }
        }
        result = client.graphql_query(config, mutation, variables)
        data = result.get('data', {}).get('productUpdate', {})

        user_errors = data.get('userErrors', [])
        if user_errors:
            raise UserError(_('Shopify product update errors: %s') % str(user_errors))

        # Update prices
        self._sync_product_prices(config, client, variants, shopify_product_id)

    # ── Build helpers ──────────────────────────────────────────────────────
    def _build_options(self, product_tmpl):
        """Build Shopify options from Odoo product attributes. Max 3."""
        options = []
        for attr_line in product_tmpl.attribute_line_ids[:3]:
            options.append({
                'name': attr_line.attribute_id.name,
                'values': attr_line.value_ids.mapped('name'),
            })
        return options

    def _save_variant_mappings_from_bulk(self, config, odoo_variants, created_variants, shopify_product_id):
        """Save shopify.product.mapping for each variant after bulk create."""
        Mapping = self.env['shopify.product.mapping']

        shopify_variants_by_sku = {}
        for node in created_variants:
            sku = node.get('sku', '')
            if sku:
                shopify_variants_by_sku[sku] = node

        for odoo_variant in odoo_variants:
            sku = odoo_variant.default_code
            if not sku:
                continue
            shopify_variant = shopify_variants_by_sku.get(sku, {})

            existing = Mapping.search([
                ('config_id', '=', config.id),
                ('product_id', '=', odoo_variant.id),
            ], limit=1)

            vals = {
                'config_id': config.id,
                'product_id': odoo_variant.id,
                'shopify_product_id': shopify_product_id,
                'shopify_variant_id': shopify_variant.get('id', ''),
                'shopify_inventory_item_id': shopify_variant.get('inventoryItem', {}).get('id', ''),
                'sku': sku,
                'last_synced': fields.Datetime.now(),
                'sync_status': 'synced' if shopify_variant.get('id') else 'error',
            }

            if existing:
                existing.write(vals)
            else:
                Mapping.create(vals)

    # ── Image sync ─────────────────────────────────────────────────────────
    def _sync_product_images(self, config, client, product_tmpl, shopify_product_id):
        """Sync product images. Skips if image unchanged (checksum comparison)."""
        if not product_tmpl.image_1920:
            return

        try:
            image_data = base64.b64decode(product_tmpl.image_1920)
            checksum = hashlib.md5(image_data).hexdigest()

            # Check if image already synced with same checksum
            # (store checksum in product.template using a custom field if needed)
            # For now, always upload on create, skip on update unless changed
            image_b64 = product_tmpl.image_1920.decode() if isinstance(
                product_tmpl.image_1920, bytes) else product_tmpl.image_1920

            mutation = """
            mutation productCreateMedia($productId: ID!, $media: [CreateMediaInput!]!) {
              productCreateMedia(productId: $productId, media: $media) {
                media { ... on MediaImage { id } }
                mediaUserErrors { field message }
              }
            }
            """
            variables = {
                'productId': shopify_product_id,
                'media': [{
                    'mediaContentType': 'IMAGE',
                    'originalSource': f'data:image/jpeg;base64,{image_b64}',
                }]
            }
            client.graphql_query(config, mutation, variables)

        except Exception as e:
            _logger.warning('Failed to sync image for product %s: %s', product_tmpl.name, str(e))
            # Image sync failure is non-blocking

    # ── Price sync ─────────────────────────────────────────────────────────
    def _sync_product_prices(self, config, client, variants, shopify_product_id):
        """Sync fixed prices per pricelist mapping to Shopify markets."""
        pricelist_mappings = self.env['shopify.pricelist.mapping'].search([
            ('config_id', '=', config.id)
        ])

        if not pricelist_mappings:
            return

        for variant in variants:
            mapping = self.env['shopify.product.mapping'].search([
                ('config_id', '=', config.id),
                ('product_id', '=', variant.id),
            ], limit=1)
            if not mapping or not mapping.shopify_variant_id:
                continue

            for pl_mapping in pricelist_mappings:
                price = pl_mapping.pricelist_id._get_product_price(
                    variant, 1.0, uom=False
                )
                self._update_variant_price(
                    config, client, shopify_product_id,
                    mapping.shopify_variant_id, price,
                    variant.default_code, pl_mapping.shopify_currency
                )

    def _update_variant_price(self, config, client, shopify_product_id,
                               shopify_variant_id, price, sku, currency_code):
        """
        Update a single variant's price via productVariantsBulkUpdate.

        NOTE: productVariantUpdate is deprecated — Shopify now requires
        the bulk endpoint even for single-variant updates.
        """
        mutation = """
        mutation productVariantsBulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
          productVariantsBulkUpdate(productId: $productId, variants: $variants) {
            productVariants { id price }
            userErrors { field message }
          }
        }
        """
        variables = {
            'productId': shopify_product_id,
            'variants': [{
                'id': shopify_variant_id,
                'price': str(price),
            }]
        }
        try:
            result = client.graphql_query(config, mutation, variables)
            data = result.get('data', {}).get('productVariantsBulkUpdate', {})
            user_errors = data.get('userErrors', [])
            if user_errors:
                _logger.warning(
                    'Failed to update price for variant %s in currency %s: %s',
                    sku, currency_code, str(user_errors)
                )
        except Exception as e:
            _logger.warning(
                'Failed to update price for variant %s in currency %s: %s',
                sku, currency_code, str(e)
            )
