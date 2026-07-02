# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ShopifyBulkSyncWizard(models.TransientModel):
    _name = 'shopify.bulk.sync.wizard'
    _description = 'Shopify Bulk Sync Wizard'

    config_id = fields.Many2one(
        'shopify.config', string='Store', required=True
    )
    sync_products = fields.Boolean(string='Sync Products', default=True)
    sync_inventory = fields.Boolean(string='Sync Inventory', default=True)
    sync_orders_since = fields.Datetime(
        string='Pull Orders Since',
        help='Leave empty to use the last sync timestamp.'
    )

    def action_run_sync(self):
        self.ensure_one()
        config = self.config_id

        results = []

        if self.sync_products:
            try:
                self.env['shopify.product.sync'].bulk_sync_products(config)
                results.append(_('✓ Products synced.'))
            except Exception as e:
                results.append(_('✗ Product sync failed: %s') % str(e))

        if self.sync_inventory:
            try:
                self.env['shopify.inventory.sync'].bulk_sync_inventory(config)
                results.append(_('✓ Inventory synced.'))
            except Exception as e:
                results.append(_('✗ Inventory sync failed: %s') % str(e))

        if self.sync_orders_since:
            try:
                config.write({'last_order_sync': self.sync_orders_since})
                self.env['shopify.order.sync'].poll_new_orders(config)
                results.append(_('✓ Orders pulled.'))
            except Exception as e:
                results.append(_('✗ Order pull failed: %s') % str(e))

        message = '\n'.join(results) if results else _('No sync actions selected.')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bulk Sync Completed'),
                'message': message,
                'type': 'success' if '✗' not in message else 'warning',
                'sticky': True,
            }
        }
