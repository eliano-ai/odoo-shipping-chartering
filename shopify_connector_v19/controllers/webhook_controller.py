# -*- coding: utf-8 -*-
import hashlib
import hmac
import base64
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class ShopifyWebhookController(http.Controller):
    """
    HTTP controller that receives incoming webhooks from Shopify.

    Security:
    - Every request is verified using HMAC-SHA256 before processing.
    - Processing is asynchronous (queue job) — we return HTTP 200 immediately.

    URL pattern: /shopify/webhook/<config_id>/<topic>
    Example: /shopify/webhook/1/orders-create
    """

    @http.route(
        '/shopify/webhook/<int:config_id>/<string:topic>',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
    )
    def receive_webhook(self, config_id, topic, **kwargs):
        """
        Main webhook receiver.
        1. Verify HMAC
        2. Return 200 immediately
        3. Queue payload for async processing
        """
        # Get raw body BEFORE any parsing
        raw_body = request.httprequest.get_data()

        # Get HMAC header
        shopify_hmac = request.httprequest.headers.get('X-Shopify-Hmac-Sha256', '')

        # Load config
        config = request.env['shopify.config'].sudo().search([
            ('id', '=', config_id),
            ('is_active', '=', True),
        ], limit=1)

        if not config:
            _logger.warning('Webhook received for unknown config_id=%d', config_id)
            return request.make_response('Not Found', status=404)

        # ── HMAC Verification (MANDATORY — never skip) ─────────────────────
        if not self._verify_hmac(raw_body, shopify_hmac, config.webhook_secret):
            _logger.warning(
                'Invalid HMAC signature for config_id=%d topic=%s — rejecting.',
                config_id, topic
            )
            return request.make_response('Unauthorized', status=401)

        # ── Return 200 IMMEDIATELY ──────────────────────────────────────────
        # Shopify requires response within 5 seconds.
        # Actual processing happens asynchronously.
        try:
            payload = json.loads(raw_body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            _logger.error('Failed to parse webhook payload: %s', str(e))
            return request.make_response('Bad Request', status=400)

        # Convert URL topic format (orders-create) to event format (orders/create)
        event_topic = topic.replace('-', '/')

        # Queue async processing
        self._queue_webhook_processing(config, event_topic, payload)

        return request.make_response('OK', status=200)

    # ── HMAC verification ──────────────────────────────────────────────────
    def _verify_hmac(self, raw_body, shopify_hmac, webhook_secret):
        """
        Verify Shopify webhook HMAC signature.
        Uses constant-time comparison to prevent timing attacks.

        raw_body: bytes (must be raw, before any parsing)
        shopify_hmac: str (base64-encoded from Shopify header)
        webhook_secret: str (from shopify.config)
        """
        if not shopify_hmac or not webhook_secret:
            return False

        try:
            secret_bytes = webhook_secret.encode('utf-8')
            computed = base64.b64encode(
                hmac.new(secret_bytes, raw_body, hashlib.sha256).digest()
            ).decode('utf-8')
            # Constant-time comparison
            return hmac.compare_digest(computed, shopify_hmac)
        except Exception as e:
            _logger.error('HMAC verification error: %s', str(e))
            return False

    # ── Queue async processing ─────────────────────────────────────────────
    def _queue_webhook_processing(self, config, topic, payload):
        """
        Queue the webhook payload for asynchronous processing.
        Uses Odoo Queue Job if available, otherwise uses a scheduled fallback.
        """
        try:
            # Try Queue Job first
            processor = request.env['shopify.webhook.processor'].sudo()
            processor.with_delay().process_webhook(config.id, topic, payload)
        except AttributeError:
            # Queue Job not available — process in a new transaction
            # (not ideal for production but workable as fallback)
            _logger.warning(
                'Queue Job not available — processing webhook %s synchronously.', topic
            )
            try:
                request.env['shopify.webhook.processor'].sudo().process_webhook(
                    config.id, topic, payload
                )
            except Exception as e:
                _logger.error('Synchronous webhook processing failed: %s', str(e))


class ShopifyWebhookProcessor(http.Controller):
    """Not an HTTP controller — used as a job target for queue_job."""
    pass
