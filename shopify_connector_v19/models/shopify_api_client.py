# -*- coding: utf-8 -*-
import time
import logging
import requests

from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Retry config
MAX_RETRIES = 5
BACKOFF_BASE = 1  # seconds — doubles each retry: 1, 2, 4, 8, 16


class ShopifyApiClient(models.AbstractModel):
    """
    Abstract model providing Shopify GraphQL API communication.
    All methods receive a shopify.config record as first arg.
    """
    _name = 'shopify.api.client'
    _description = 'Shopify API Client'

    # ── Core GraphQL request ───────────────────────────────────────────────
    def graphql_query(self, config, query, variables=None):
        """
        Execute a GraphQL query/mutation against Shopify Admin API.
        Handles rate limiting, retries, and error classification.

        Returns parsed JSON response dict.
        Raises UserError on unrecoverable errors.
        """
        url = config._get_graphql_url()
        headers = {
            'X-Shopify-Access-Token': config.access_token,
            'Content-Type': 'application/json',
        }
        payload = {'query': query}
        if variables:
            payload['variables'] = variables

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = requests.post(
                    url, json=payload, headers=headers, timeout=30
                )
                self._handle_rate_limit(response)

                if response.status_code == 200:
                    data = response.json()
                    if 'errors' in data:
                        error_msg = str(data['errors'])
                        _logger.error('Shopify GraphQL errors: %s', error_msg)
                        raise UserError(_('Shopify API error: %s') % error_msg)
                    return data

                elif response.status_code == 429:
                    # Rate limited — wait and retry
                    retry_after = float(response.headers.get('Retry-After', 2))
                    _logger.warning(
                        'Shopify rate limit hit. Waiting %.1fs before retry %d/%d',
                        retry_after, attempt, MAX_RETRIES
                    )
                    time.sleep(retry_after)
                    continue

                elif response.status_code in (500, 502, 503, 504):
                    # Transient server error — exponential backoff
                    wait = BACKOFF_BASE * (2 ** (attempt - 1))
                    _logger.warning(
                        'Shopify server error %d. Waiting %ds. Attempt %d/%d',
                        response.status_code, wait, attempt, MAX_RETRIES
                    )
                    time.sleep(wait)
                    continue

                elif response.status_code == 401:
                    raise UserError(_(
                        'Shopify authentication failed (HTTP 401). '
                        'Please verify the Access Token in store configuration: %s'
                    ) % config.name)

                elif response.status_code == 404:
                    raise UserError(_(
                        'Shopify resource not found (HTTP 404). '
                        'The requested resource may have been deleted in Shopify.'
                    ))

                else:
                    # Other client errors — do not retry
                    raise UserError(_(
                        'Shopify API returned HTTP %(code)d: %(body)s',
                        code=response.status_code,
                        body=response.text[:500]
                    ))

            except requests.exceptions.Timeout:
                wait = BACKOFF_BASE * (2 ** (attempt - 1))
                _logger.warning(
                    'Shopify API timeout. Waiting %ds. Attempt %d/%d',
                    wait, attempt, MAX_RETRIES
                )
                if attempt < MAX_RETRIES:
                    time.sleep(wait)
                    continue
                raise UserError(_('Shopify API timed out after %d attempts.') % MAX_RETRIES)

            except requests.exceptions.ConnectionError as e:
                wait = BACKOFF_BASE * (2 ** (attempt - 1))
                _logger.warning('Shopify connection error: %s. Attempt %d/%d', str(e), attempt, MAX_RETRIES)
                if attempt < MAX_RETRIES:
                    time.sleep(wait)
                    continue
                raise UserError(_('Cannot connect to Shopify: %s') % str(e))

        raise UserError(_('Shopify API request failed after %d attempts.') % MAX_RETRIES)

    # ── Rate limit handling ────────────────────────────────────────────────
    def _handle_rate_limit(self, response):
        """
        For GraphQL: check X-GraphQL-Cost-Include-Fields header.
        Proactively slow down if cost is high.
        """
        # GraphQL cost-based throttling
        cost_header = response.headers.get('X-GraphQL-Cost-Include-Fields')
        if cost_header:
            try:
                parts = cost_header.split('/')
                if len(parts) == 2:
                    used = float(parts[0])
                    limit = float(parts[1])
                    if limit > 0 and (used / limit) > 0.85:
                        _logger.debug('Shopify GraphQL cost high (%.0f/%.0f), adding delay.', used, limit)
                        time.sleep(0.5)
            except (ValueError, IndexError):
                pass

    # ── Paginated query helper ─────────────────────────────────────────────
    def graphql_paginate(self, config, query_template, data_path, variables=None):
        """
        Execute a paginated GraphQL query, yielding all results.

        query_template must accept $cursor variable and return pageInfo.
        data_path is a list of keys to reach the edges list, e.g. ['products', 'edges'].
        """
        cursor = None
        variables = variables or {}

        while True:
            variables['cursor'] = cursor
            result = self.graphql_query(config, query_template, variables)

            data = result.get('data', {})
            node = data
            for key in data_path[:-1]:
                node = node.get(key, {})

            edges_key = data_path[-1]
            connection = node.get(edges_key.replace('edges', ''), node)
            edges = connection.get('edges', [])
            page_info = connection.get('pageInfo', {})

            for edge in edges:
                yield edge.get('node', edge)

            if not page_info.get('hasNextPage'):
                break
            cursor = page_info.get('endCursor')
