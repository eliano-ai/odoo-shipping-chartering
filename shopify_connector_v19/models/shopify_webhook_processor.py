# -*- coding: utf-8 -*-
import logging

from odoo import models, api, _

_logger = logging.getLogger(__name__)


class ShopifyWebhookProcessor(models.AbstractModel):
    """
    Processes Shopify webhook payloads asynchronously.
    Called by queue_job after the HTTP controller acknowledges the webhook.
    """
    _name = 'shopify.webhook.processor'
    _description = 'Shopify Webhook Payload Processor'

    def process_webhook(self, config_id, topic, payload):
        """
        Route webhook to the appropriate sync handler based on topic.
        """
        config = self.env['shopify.config'].browse(config_id)
        if not config.exists() or not config.is_active:
            _logger.warning('Webhook for inactive/missing config_id=%d — skipping.', config_id)
            return

        _logger.info('Processing webhook: topic=%s store=%s', topic, config.name)

        handlers = {
            'orders/create': self._handle_order_create,
            'orders/updated': self._handle_order_updated,
            'orders/cancelled': self._handle_order_cancelled,
            'orders/fulfilled': self._handle_order_fulfilled,
            'orders/partially_fulfilled': self._handle_order_fulfilled,
            'refunds/create': self._handle_refund_create,
            'customers/create': self._handle_customer_upsert,
            'customers/update': self._handle_customer_upsert,
            'app/uninstalled': self._handle_app_uninstalled,
        }

        handler = handlers.get(topic)
        if handler:
            try:
                handler(config, payload)
            except Exception as e:
                _logger.error(
                    'Webhook handler error for topic=%s store=%s: %s',
                    topic, config.name, str(e)
                )
                raise  # Re-raise so queue_job can retry
        else:
            _logger.info('No handler for webhook topic: %s — ignoring.', topic)

    # ── Handlers ───────────────────────────────────────────────────────────

    def _handle_order_create(self, config, payload):
        if not config.sync_order:
            return
        self.env['shopify.order.sync'].process_shopify_order(config, payload)

    def _handle_order_updated(self, config, payload):
        """Handle order updates — currently updates sync status."""
        shopify_order_id = str(payload.get('id', ''))
        financial_status = payload.get('financial_status', '')
        fulfillment_status = payload.get('fulfillment_status', '')

        mapping = self.env['shopify.order.mapping'].search([
            ('config_id', '=', config.id),
            ('shopify_order_id', '=', shopify_order_id),
        ], limit=1)

        if mapping:
            mapping.write({
                'shopify_financial_status': financial_status,
                'shopify_fulfillment_status': fulfillment_status,
            })
            if mapping.sale_order_id:
                mapping.sale_order_id.write({
                    'shopify_financial_status': financial_status,
                })
        else:
            # Order not yet in Odoo — try to import it
            if config.sync_order:
                self.env['shopify.order.sync'].process_shopify_order(config, payload)

    def _handle_order_cancelled(self, config, payload):
        if not config.sync_order:
            return
        self.env['shopify.refund.sync'].process_cancellation(config, payload)

    def _handle_order_fulfilled(self, config, payload):
        """Log fulfillment from Shopify side (tracking already pushed from Odoo)."""
        shopify_order_id = str(payload.get('id', ''))
        mapping = self.env['shopify.order.mapping'].search([
            ('config_id', '=', config.id),
            ('shopify_order_id', '=', shopify_order_id),
        ], limit=1)
        if mapping:
            mapping.write({'shopify_fulfillment_status': 'fulfilled'})

    def _handle_refund_create(self, config, payload):
        """Process refund payload from Shopify."""
        self.env['shopify.refund.sync'].process_refund(config, payload)

    def _handle_customer_upsert(self, config, payload):
        """Handle customer create/update from Shopify."""
        customer_sync = self.env['shopify.customer.sync']
        customer_sync.get_or_create_partner(config, payload)

    def _handle_app_uninstalled(self, config, payload):
        """Shopify app was uninstalled — deactivate config and alert."""
        _logger.warning(
            'Shopify app uninstalled for store %s — deactivating config.',
            config.name
        )
        config.write({'is_active': False})
        self.env['shopify.sync.log'].log_sync(
            config, 'webhook', 'pull', 'needs_review',
            record_name='App Uninstalled',
            error_msg='Shopify app was uninstalled. Configuration deactivated. Please re-install the Custom App.'
        )
