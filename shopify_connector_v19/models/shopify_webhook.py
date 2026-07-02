# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, _

_logger = logging.getLogger(__name__)

WEBHOOK_TOPICS = [
    'orders/create',
    'orders/updated',
    'orders/cancelled',
    'orders/fulfilled',
    'orders/partially_fulfilled',
    'refunds/create',
    'customers/create',
    'customers/update',
    'app/uninstalled',
]


class ShopifyWebhookManager(models.AbstractModel):
    _name = 'shopify.webhook.manager'
    _description = 'Shopify Webhook Registration Manager'

    def register_all_webhooks(self, config):
        """Register all required webhooks to Shopify for the given config."""
        client = self.env['shopify.api.client']
        base_url = self._get_webhook_base_url(config)

        # First, fetch existing webhooks to avoid duplicates
        existing = self._get_existing_webhooks(config, client)
        existing_topics = {w.get('topic') for w in existing}

        registered = []
        for topic in WEBHOOK_TOPICS:
            if topic in existing_topics:
                _logger.info('Webhook %s already registered for store %s.', topic, config.name)
                registered.append(topic)
                continue

            callback_url = f"{base_url}/shopify/webhook/{config.id}/{topic.replace('/', '-')}"
            try:
                self._register_webhook(config, client, topic, callback_url)
                registered.append(topic)
                _logger.info('Registered webhook: %s → %s', topic, callback_url)
            except Exception as e:
                _logger.error('Failed to register webhook %s: %s', topic, str(e))

        return registered

    def _register_webhook(self, config, client, topic, callback_url):
        """Register a single webhook subscription."""
        mutation = """
        mutation webhookSubscriptionCreate($topic: WebhookSubscriptionTopic!, $webhookSubscription: WebhookSubscriptionInput!) {
          webhookSubscriptionCreate(topic: $topic, webhookSubscription: $webhookSubscription) {
            webhookSubscription { id topic endpoint { __typename } }
            userErrors { field message }
          }
        }
        """
        # Convert REST-style topic to GraphQL enum format
        gql_topic = topic.upper().replace('/', '_')

        variables = {
            'topic': gql_topic,
            'webhookSubscription': {
                'callbackUrl': callback_url,
                'format': 'JSON',
            }
        }
        result = client.graphql_query(config, mutation, variables)
        data = result.get('data', {}).get('webhookSubscriptionCreate', {})
        user_errors = data.get('userErrors', [])
        if user_errors:
            raise Exception(f'Webhook registration error: {user_errors}')

    def _get_existing_webhooks(self, config, client):
        """Fetch all existing webhook subscriptions from Shopify."""
        query = """
        {
          webhookSubscriptions(first: 50) {
            edges {
              node {
                id
                topic
                endpoint {
                  __typename
                  ... on WebhookHttpEndpoint { callbackUrl }
                }
              }
            }
          }
        }
        """
        result = client.graphql_query(config, query)
        edges = result.get('data', {}).get('webhookSubscriptions', {}).get('edges', [])
        return [edge.get('node', {}) for edge in edges]

    def _get_webhook_base_url(self, config):
        """Get the base URL for webhook callbacks (Odoo instance URL)."""
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        return base.rstrip('/')

    def verify_all_webhooks(self, config):
        """
        Called by daily cron. Checks that all required webhooks are still registered.
        Re-registers any that are missing.
        """
        client = self.env['shopify.api.client']
        existing = self._get_existing_webhooks(config, client)
        existing_topics = {w.get('topic', '').lower().replace('_', '/') for w in existing}

        missing = [t for t in WEBHOOK_TOPICS if t not in existing_topics]
        if missing:
            _logger.warning(
                'Missing webhooks for store %s: %s — re-registering.',
                config.name, missing
            )
            base_url = self._get_webhook_base_url(config)
            for topic in missing:
                callback_url = f"{base_url}/shopify/webhook/{config.id}/{topic.replace('/', '-')}"
                try:
                    self._register_webhook(config, client, topic, callback_url)
                except Exception as e:
                    _logger.error('Failed to re-register webhook %s: %s', topic, str(e))
