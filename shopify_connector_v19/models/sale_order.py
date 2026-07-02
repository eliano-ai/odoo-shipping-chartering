# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ── Shopify info fields (read-only, for reference) ─────────────────────
    shopify_order_id = fields.Char(
        string='Shopify Order ID', readonly=True, copy=False,
        help='Internal Shopify order ID.'
    )
    shopify_financial_status = fields.Char(
        string='Shopify Payment Status', readonly=True, copy=False
    )
    shopify_payment_gateway = fields.Char(
        string='Shopify Payment Gateway', readonly=True, copy=False
    )
    shopify_amount_paid = fields.Float(
        string='Amount Paid (Shopify)', readonly=True, copy=False,
        help='Amount paid as reported by Shopify. For reference/reconciliation only.'
    )
    shopify_sync_status = fields.Selection(
        [('synced', 'Synced'), ('pending', 'Pending'),
         ('error', 'Error'), ('needs_review', 'Needs Review')],
        string='Shopify Sync Status', readonly=True, copy=False
    )


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _action_done(self):
        """
        Override to trigger Shopify tracking sync after delivery is validated.
        Only triggers for outgoing pickings linked to a Sale Order.
        """
        result = super()._action_done()

        for picking in self.filtered(
            lambda p: p.picking_type_code == 'outgoing' and p.sale_id
        ):
            # Find active Shopify configs for the picking's company
            configs = self.env['shopify.config'].search([
                ('is_active', '=', True),
                ('sync_order', '=', True),
                ('company_id', '=', picking.company_id.id),
            ])
            for config in configs:
                try:
                    tracking_sync = self.env['shopify.tracking.sync']
                    tracking_sync.sudo().with_delay().sync_tracking_to_shopify(config, picking)
                except AttributeError:
                    # Queue job not available — run synchronously
                    try:
                        self.env['shopify.tracking.sync'].sync_tracking_to_shopify(config, picking)
                    except Exception as e:
                        _logger.error(
                            'Failed to trigger tracking sync for picking %s: %s',
                            picking.name, str(e)
                        )

        return result


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        """
        Override to trigger inventory sync after stock moves are completed.
        """
        result = super()._action_done(cancel_backorder=cancel_backorder)

        products = self.mapped('product_id')
        if not products:
            return result

        configs = self.env['shopify.config'].search([
            ('is_active', '=', True),
            ('sync_inventory', '=', True),
        ])

        for config in configs:
            try:
                inv_sync = self.env['shopify.inventory.sync']
                for product in products:
                    try:
                        inv_sync.sudo().with_delay().sync_inventory_for_product(config, product)
                    except AttributeError:
                        inv_sync.sync_inventory_for_product(config, product)
            except Exception as e:
                _logger.error(
                    'Failed to trigger inventory sync after stock move: %s', str(e)
                )

        return result
