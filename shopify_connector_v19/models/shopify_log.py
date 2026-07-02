# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class ShopifySyncLog(models.Model):
    _name = 'shopify.sync.log'
    _description = 'Shopify Sync Activity Log'
    _order = 'created_at desc'

    # Odoo 19: _rec_name still works but display_name is computed via
    # _compute_display_name instead of deprecated name_get()
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.record_name or f'Log #{rec.id}'

    config_id = fields.Many2one(
        'shopify.config', string='Store Config',
        required=True, ondelete='cascade', index=True
    )
    sync_type = fields.Selection([
        ('product', 'Product'),
        ('inventory', 'Inventory'),
        ('order', 'Order'),
        ('customer', 'Customer'),
        ('tracking', 'Tracking'),
        ('refund', 'Refund'),
        ('webhook', 'Webhook'),
        ('reconciliation', 'Reconciliation'),
    ], string='Sync Type', required=True, index=True)

    direction = fields.Selection([
        ('push', 'Push (Odoo → Shopify)'),
        ('pull', 'Pull (Shopify → Odoo)'),
    ], string='Direction', required=True)

    status = fields.Selection([
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
        ('needs_review', 'Needs Review'),
    ], string='Status', required=True, default='pending', index=True)

    record_name = fields.Char(string='Record')
    odoo_record_ref = fields.Char(string='Odoo Reference')
    shopify_record_ref = fields.Char(string='Shopify Reference')
    error_message = fields.Text(string='Error Message')
    request_payload = fields.Text(string='Request Payload (JSON)')
    response_payload = fields.Text(string='Response Payload (JSON)')
    duration_ms = fields.Integer(string='Duration (ms)')
    created_at = fields.Datetime(
        string='Created At', default=fields.Datetime.now, index=True
    )
    retry_count = fields.Integer(string='Retry Count', default=0)

    @api.model
    def log_sync(self, config, sync_type, direction, status,
                 record_name='', odoo_ref='', shopify_ref='', shopify_record_ref='',
                 error_msg='', request_payload='', response_payload='',
                 duration_ms=0):
        return self.create({
            'config_id': config.id,
            'sync_type': sync_type,
            'direction': direction,
            'status': status,
            'record_name': record_name,
            'odoo_record_ref': odoo_ref,
            'shopify_record_ref': shopify_record_ref or shopify_ref,
            'error_message': error_msg,
            'request_payload': request_payload,
            'response_payload': response_payload,
            'duration_ms': duration_ms,
        })

    @api.model
    def cleanup_old_logs(self):
        from datetime import datetime, timedelta
        cutoff_success = datetime.now() - timedelta(days=30)
        cutoff_failed = datetime.now() - timedelta(days=90)

        self.search([
            ('status', '=', 'success'),
            ('created_at', '<', cutoff_success)
        ]).unlink()

        self.search([
            ('status', 'in', ['failed', 'skipped']),
            ('created_at', '<', cutoff_failed)
        ]).unlink()

        _logger.info('Shopify log cleanup completed.')
