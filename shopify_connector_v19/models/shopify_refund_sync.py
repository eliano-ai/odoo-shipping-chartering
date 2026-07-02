# -*- coding: utf-8 -*-
import logging
import time

from odoo import models, fields, _

_logger = logging.getLogger(__name__)


class ShopifyRefundSync(models.AbstractModel):
    _name = 'shopify.refund.sync'
    _description = 'Shopify Refund & Cancellation Sync Engine'

    def process_refund(self, config, refund_data):
        """
        Process a refund from Shopify.
        Creates Credit Note in Odoo, and Return Picking if physical return exists.
        """
        start = time.time()
        Log = self.env['shopify.sync.log']

        shopify_order_id = str(refund_data.get('orderId', ''))
        refund_id = str(refund_data.get('id', ''))

        order_mapping = self.env['shopify.order.mapping'].search([
            ('config_id', '=', config.id),
            ('shopify_order_id', '=', shopify_order_id),
        ], limit=1)

        if not order_mapping or not order_mapping.sale_order_id:
            Log.log_sync(
                config, 'refund', 'pull', 'needs_review',
                record_name=f'Refund {refund_id}',
                shopify_record_ref=shopify_order_id,
                error_msg='Corresponding Sales Order not found in Odoo.'
            )
            return

        sale_order = order_mapping.sale_order_id

        try:
            refund_amount = float(
                refund_data.get('totalRefundedSet', {}).get('shopMoney', {}).get('amount', 0) or 0
            )

            # Sanity check: refund should not exceed original order amount
            if refund_amount > sale_order.amount_total:
                Log.log_sync(
                    config, 'refund', 'pull', 'needs_review',
                    record_name=f'Refund {refund_id}',
                    odoo_ref=sale_order.name,
                    shopify_record_ref=shopify_order_id,
                    error_msg=_(
                        'Refund amount (%.2f) exceeds SO total (%.2f). Manual review required.'
                    ) % (refund_amount, sale_order.amount_total)
                )
                return

            # Check if there are items being returned physically
            refund_line_items = refund_data.get('refundLineItems', {}).get('edges', [])
            has_physical_return = any(
                edge.get('node', {}).get('restockType') != 'NO_RESTOCK'
                for edge in refund_line_items
            )

            if has_physical_return:
                self._create_return_picking(config, sale_order, refund_line_items)

            # Create Credit Note
            credit_note = self._create_credit_note(config, sale_order, refund_amount, refund_id)

            duration = int((time.time() - start) * 1000)
            Log.log_sync(
                config, 'refund', 'pull', 'success',
                record_name=f'Refund {refund_id}',
                odoo_ref=credit_note.name if credit_note else '',
                shopify_record_ref=shopify_order_id,
                duration_ms=duration
            )

        except Exception as e:
            duration = int((time.time() - start) * 1000)
            Log.log_sync(
                config, 'refund', 'pull', 'failed',
                record_name=f'Refund {refund_id}',
                odoo_ref=sale_order.name,
                shopify_record_ref=shopify_order_id,
                error_msg=str(e),
                duration_ms=duration
            )
            _logger.error('Failed to process refund %s: %s', refund_id, str(e))

    def _create_credit_note(self, config, sale_order, refund_amount, refund_ref):
        """Create and post a credit note for the given refund amount."""
        # Find the original invoice
        invoices = sale_order.invoice_ids.filtered(
            lambda inv: inv.move_type == 'out_invoice' and inv.state == 'posted'
        )

        if invoices:
            invoice = invoices[0]
            credit_note_wizard = self.env['account.move.reversal'].with_context(
                active_ids=invoice.ids,
                active_model='account.move'
            ).create({
                'reason': f'Shopify Refund {refund_ref}',
                'refund_method': 'refund',
            })
            result = credit_note_wizard.reverse_moves()
            credit_note = self.env['account.move'].browse(result.get('res_id'))

            # Adjust credit note amount if partial refund
            if abs(credit_note.amount_total - refund_amount) > 0.01:
                # For partial refunds, adjust lines proportionally
                # This is a simplified approach — complex partial refunds may need manual adjustment
                _logger.warning(
                    'Partial refund detected for SO %s. '
                    'Credit note amount %.2f vs refund amount %.2f. '
                    'Manual adjustment may be needed.',
                    sale_order.name, credit_note.amount_total, refund_amount
                )

            return credit_note
        else:
            # No posted invoice — create standalone credit note
            _logger.warning(
                'No posted invoice for SO %s. Creating standalone credit note.',
                sale_order.name
            )
            return None

    def _create_return_picking(self, config, sale_order, refund_line_items):
        """Create a return picking for physical product returns."""
        pickings = sale_order.picking_ids.filtered(
            lambda p: p.state == 'done' and p.picking_type_code == 'outgoing'
        )
        if not pickings:
            _logger.warning(
                'No completed delivery found for SO %s — cannot create return picking.',
                sale_order.name
            )
            return

        picking = pickings[0]
        return_wizard = self.env['stock.return.picking'].with_context(
            active_id=picking.id,
            active_model='stock.picking'
        ).create({})

        # Update quantities to return based on refund line items
        return_wizard.product_return_moves.write({'quantity': 0})
        for edge in refund_line_items:
            node = edge.get('node', {})
            sku = node.get('lineItem', {}).get('sku', '')
            qty = float(node.get('quantity', 0))

            if sku:
                for return_line in return_wizard.product_return_moves:
                    if return_line.product_id.default_code == sku:
                        return_line.write({'quantity': qty})
                        break

        return_wizard.create_returns()

    def process_cancellation(self, config, order_data):
        """
        Process an order cancellation from Shopify.
        Cancels the SO if possible, otherwise flags for review.
        """
        start = time.time()
        Log = self.env['shopify.sync.log']

        shopify_order_id = str(order_data.get('id', ''))
        shopify_order_name = order_data.get('name', '')

        order_mapping = self.env['shopify.order.mapping'].search([
            ('config_id', '=', config.id),
            ('shopify_order_id', '=', shopify_order_id),
        ], limit=1)

        if not order_mapping or not order_mapping.sale_order_id:
            return

        sale_order = order_mapping.sale_order_id

        try:
            # Check if there are any done delivery orders
            done_pickings = sale_order.picking_ids.filtered(lambda p: p.state == 'done')
            if done_pickings:
                # Cannot auto-cancel — flag for manual review
                order_mapping.write({'sync_status': 'needs_review'})
                Log.log_sync(
                    config, 'order', 'pull', 'needs_review',
                    record_name=shopify_order_name,
                    odoo_ref=sale_order.name,
                    shopify_record_ref=shopify_order_id,
                    error_msg=_(
                        'Order cancelled in Shopify but SO has completed deliveries. '
                        'Manual cancellation required.'
                    )
                )
                return

            # Cancel the SO
            if sale_order.state in ('draft', 'sent', 'sale'):
                sale_order.action_cancel()
                order_mapping.write({'sync_status': 'synced'})

            duration = int((time.time() - start) * 1000)
            Log.log_sync(
                config, 'order', 'pull', 'success',
                record_name=f'Cancelled: {shopify_order_name}',
                odoo_ref=sale_order.name,
                shopify_record_ref=shopify_order_id,
                duration_ms=duration
            )

        except Exception as e:
            Log.log_sync(
                config, 'order', 'pull', 'failed',
                record_name=shopify_order_name,
                odoo_ref=sale_order.name,
                shopify_record_ref=shopify_order_id,
                error_msg=str(e),
            )
            _logger.error('Failed to cancel order %s: %s', shopify_order_name, str(e))
