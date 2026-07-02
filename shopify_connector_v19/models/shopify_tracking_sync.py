# -*- coding: utf-8 -*-
import logging
import time

from odoo import models, fields, _

_logger = logging.getLogger(__name__)


class ShopifyTrackingSync(models.AbstractModel):
    _name = 'shopify.tracking.sync'
    _description = 'Shopify Tracking Number Sync Engine'

    def sync_tracking_to_shopify(self, config, stock_picking):
        """
        Called after a Delivery Order is validated in Odoo.
        Sends tracking number and carrier info to Shopify,
        which triggers a fulfillment notification to the customer.
        """
        start = time.time()
        Log = self.env['shopify.sync.log']
        client = self.env['shopify.api.client']

        # Find the related Sales Order
        sale_order = stock_picking.sale_id
        if not sale_order:
            return

        # Find Shopify order mapping
        order_mapping = self.env['shopify.order.mapping'].search([
            ('config_id', '=', config.id),
            ('sale_order_id', '=', sale_order.id),
        ], limit=1)

        if not order_mapping:
            _logger.debug(
                'No Shopify order mapping for SO %s — skipping tracking sync.',
                sale_order.name
            )
            return

        tracking_number = stock_picking.carrier_tracking_ref or ''
        carrier_name = stock_picking.carrier_id.name if stock_picking.carrier_id else ''

        if not tracking_number:
            _logger.debug(
                'No tracking number on picking %s — skipping tracking sync.',
                stock_picking.name
            )
            return

        try:
            # Get the fulfillment order ID from Shopify
            fulfillment_order_id = self._get_fulfillment_order_id(
                config, client, order_mapping.shopify_order_id
            )

            if not fulfillment_order_id:
                raise Exception(_(
                    'Could not find fulfillment order for Shopify order %s'
                ) % order_mapping.shopify_order_name)

            # Create fulfillment in Shopify
            mutation = """
            mutation fulfillmentCreateV2($fulfillment: FulfillmentV2Input!) {
              fulfillmentCreateV2(fulfillment: $fulfillment) {
                fulfillment {
                  id
                  status
                  trackingInfo { number url company }
                }
                userErrors { field message }
              }
            }
            """
            variables = {
                'fulfillment': {
                    'lineItemsByFulfillmentOrder': [{
                        'fulfillmentOrderId': fulfillment_order_id,
                    }],
                    'trackingInfo': {
                        'number': tracking_number,
                        'company': carrier_name,
                    },
                    'notifyCustomer': True,
                }
            }

            result = client.graphql_query(config, mutation, variables)
            data = result.get('data', {}).get('fulfillmentCreateV2', {})
            user_errors = data.get('userErrors', [])
            if user_errors:
                raise Exception(f'Shopify fulfillment errors: {user_errors}')

            duration = int((time.time() - start) * 1000)
            Log.log_sync(
                config, 'tracking', 'push', 'success',
                record_name=f'{order_mapping.shopify_order_name} — {tracking_number}',
                odoo_ref=sale_order.name,
                shopify_record_ref=order_mapping.shopify_order_id,
                duration_ms=duration
            )
            _logger.info(
                'Tracking %s synced to Shopify for order %s.',
                tracking_number, order_mapping.shopify_order_name
            )

        except Exception as e:
            duration = int((time.time() - start) * 1000)
            Log.log_sync(
                config, 'tracking', 'push', 'failed',
                record_name=order_mapping.shopify_order_name,
                odoo_ref=sale_order.name,
                shopify_record_ref=order_mapping.shopify_order_id,
                error_msg=str(e),
                duration_ms=duration
            )
            _logger.error(
                'Failed to sync tracking for order %s: %s',
                order_mapping.shopify_order_name, str(e)
            )

    def _get_fulfillment_order_id(self, config, client, shopify_order_id):
        """Fetch the open fulfillment order ID from Shopify."""
        query = """
        query getFulfillmentOrders($orderId: ID!) {
          order(id: $orderId) {
            fulfillmentOrders(first: 10) {
              edges {
                node {
                  id
                  status
                }
              }
            }
          }
        }
        """
        variables = {'orderId': shopify_order_id}
        result = client.graphql_query(config, query, variables)
        edges = (
            result.get('data', {})
            .get('order', {})
            .get('fulfillmentOrders', {})
            .get('edges', [])
        )
        for edge in edges:
            node = edge.get('node', {})
            if node.get('status') in ('OPEN', 'IN_PROGRESS'):
                return node.get('id')
        return None
