# -*- coding: utf-8 -*-
import logging
import time

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class ShopifyInventorySync(models.AbstractModel):
    _name = 'shopify.inventory.sync'
    _description = 'Shopify Inventory Sync Engine'

    def sync_inventory_for_product(self, config, product):
        """
        Sync inventory levels for a single product.product to all
        mapped Shopify locations.
        """
        client = self.env['shopify.api.client']
        Log = self.env['shopify.sync.log']

        mapping = self.env['shopify.product.mapping'].search([
            ('config_id', '=', config.id),
            ('product_id', '=', product.id),
        ], limit=1)

        if not mapping or not mapping.shopify_inventory_item_id:
            _logger.debug(
                'No Shopify mapping found for product %s — skipping inventory sync.',
                product.default_code
            )
            return

        location_mappings = self.env['shopify.location.mapping'].search([
            ('config_id', '=', config.id)
        ])

        for loc_mapping in location_mappings:
            try:
                qty = self._get_available_qty(product, loc_mapping.warehouse_id)
                # Never push negative stock to Shopify
                qty = max(0, int(qty))

                self._set_inventory_level(
                    config, client,
                    shopify_location_id=loc_mapping.shopify_location_id,
                    inventory_item_id=mapping.shopify_inventory_item_id,
                    available=qty
                )

                Log.log_sync(
                    config, 'inventory', 'push', 'success',
                    record_name=product.default_code or product.name,
                    odoo_ref=str(product.id),
                    shopify_record_ref=mapping.shopify_inventory_item_id,
                )

            except Exception as e:
                error_str = str(e)
                if 'could not be found' in error_str:
                    _logger.warning(
                        'Stale inventory mapping for product %s — clearing for re-sync.',
                        product.default_code
                    )
                    mapping.unlink()
                    Log.log_sync(
                        config, 'inventory', 'push', 'skipped',
                        record_name=product.default_code or product.name,
                        odoo_ref=str(product.id),
                        error_msg='Stale Shopify mapping cleared — will be recreated on next product sync.',
                    )
                    return
                Log.log_sync(
                    config, 'inventory', 'push', 'failed',
                    record_name=product.default_code or product.name,
                    odoo_ref=str(product.id),
                    error_msg=error_str,
                )
                _logger.error(
                    'Failed to sync inventory for product %s to location %s: %s',
                    product.default_code, loc_mapping.shopify_location_name, error_str
                )

    def bulk_sync_inventory(self, config):
        """Sync inventory for all mapped products."""
        mappings = self.env['shopify.product.mapping'].search([
            ('config_id', '=', config.id),
            ('shopify_inventory_item_id', '!=', False),
        ])
        _logger.info(
            'Starting bulk inventory sync: %d variants for store %s',
            len(mappings), config.name
        )
        for mapping in mappings:
            self.sync_inventory_for_product(config, mapping.product_id)

    def sync_inventory_after_stock_move(self, config, stock_move):
        """
        Called after a stock.move is done.
        Syncs inventory for all products involved in the move.
        """
        products = stock_move.mapped('move_line_ids.product_id')
        for product in products:
            self.sync_inventory_for_product(config, product)

    # ── Shopify API call ───────────────────────────────────────────────────
    def _set_inventory_level(self, config, client, shopify_location_id,
                             inventory_item_id, available):
        """Set inventory level for a specific item at a specific location."""
        mutation = """
        mutation inventorySetOnHandQuantities($input: InventorySetOnHandQuantitiesInput!) {
          inventorySetOnHandQuantities(input: $input) {
            inventoryAdjustmentGroup {
              id
            }
            userErrors { field message }
          }
        }
        """
        variables = {
            'input': {
                'reason': 'correction',
                'setQuantities': [{
                    'inventoryItemId': inventory_item_id,
                    'locationId': shopify_location_id,
                    'quantity': available,
                }]
            }
        }
        result = client.graphql_query(config, mutation, variables)
        data = result.get('data', {}).get('inventorySetOnHandQuantities', {})
        user_errors = data.get('userErrors', [])
        if user_errors:
            from odoo.exceptions import UserError
            raise UserError(_('Shopify inventory update error: %s') % str(user_errors))

    # ── Qty calculation ────────────────────────────────────────────────────
    def _get_available_qty(self, product, warehouse):
        """
        Get qty available (on hand minus reserved) for a product in a warehouse.
        This is the qty Shopify should display as purchaseable.
        """
        domain = [
            ('product_id', '=', product.id),
            ('location_id.warehouse_id', '=', warehouse.id),
            ('location_id.usage', '=', 'internal'),
        ]
        quants = self.env['stock.quant'].search(domain)
        qty_on_hand = sum(quants.mapped('quantity'))
        qty_reserved = sum(quants.mapped('reserved_quantity'))
        return qty_on_hand - qty_reserved

    # ── Reconciliation ─────────────────────────────────────────────────────
    def reconcile_inventory(self, config):
        """
        Daily reconciliation: compare Odoo stock vs Shopify inventory levels.
        Flags discrepancies in log for review.
        """
        Log = self.env['shopify.sync.log']
        client = self.env['shopify.api.client']

        mappings = self.env['shopify.product.mapping'].search([
            ('config_id', '=', config.id),
            ('shopify_inventory_item_id', '!=', False),
        ])

        discrepancies = 0
        for mapping in mappings:
            try:
                location_mappings = self.env['shopify.location.mapping'].search([
                    ('config_id', '=', config.id)
                ])
                for loc_mapping in location_mappings:
                    odoo_qty = max(
                        0,
                        int(self._get_available_qty(mapping.product_id, loc_mapping.warehouse_id))
                    )
                    shopify_qty = self._get_shopify_inventory_level(
                        config, client,
                        mapping.shopify_inventory_item_id,
                        loc_mapping.shopify_location_id
                    )

                    if odoo_qty != shopify_qty:
                        discrepancies += 1
                        Log.log_sync(
                            config, 'reconciliation', 'push', 'needs_review',
                            record_name=mapping.product_id.default_code or mapping.product_id.name,
                            odoo_ref=str(odoo_qty),
                            shopify_record_ref=str(shopify_qty),
                            error_msg=f'Odoo qty={odoo_qty}, Shopify qty={shopify_qty}. Consider re-syncing.'
                        )
            except Exception as e:
                _logger.warning('Reconciliation error for product %s: %s', mapping.sku, str(e))

        _logger.info(
            'Inventory reconciliation done for store %s: %d discrepancies found.',
            config.name, discrepancies
        )

    def _get_shopify_inventory_level(self, config, client, inventory_item_id, location_id):
        """Fetch current inventory level from Shopify for a specific item/location."""
        query = """
        query getInventoryLevel($inventoryItemId: ID!, $locationId: ID!) {
          inventoryItem(id: $inventoryItemId) {
            inventoryLevel(locationId: $locationId) {
              quantities(names: ["available"]) {
                name
                quantity
              }
            }
          }
        }
        """
        variables = {
            'inventoryItemId': inventory_item_id,
            'locationId': location_id,
        }
        result = client.graphql_query(config, query, variables)
        try:
            quantities = (
                result['data']['inventoryItem']['inventoryLevel']['quantities']
            )
            for q in quantities:
                if q['name'] == 'available':
                    return q['quantity']
        except (KeyError, TypeError):
            pass
        return 0
