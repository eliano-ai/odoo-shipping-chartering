# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FleetVehicleBunkerManagement(models.Model):
    _inherit = 'fleet.vehicle'

    bunker_variance_threshold_pct = fields.Float(
        string='Override Threshold Variance ROB (%)',
        help='Ambang batas variance ROB reconciliation khusus kapal ini. '
             'Kosongkan/0 untuk pakai default global perusahaan.',
    )
    bunker_inquiry_ids = fields.One2many(
        'vessel.bunker.inquiry', 'vessel_id', string='Bunker Inquiries',
    )
    rob_reconciliation_ids = fields.One2many(
        'vessel.bunker.rob.reconciliation', compute='_compute_rob_reconciliation_ids',
        string='ROB Reconciliations',
    )

    @api.depends('voyage_ids.rob_reconciliation_ids')
    def _compute_rob_reconciliation_ids(self):
        for vehicle in self:
            vehicle.rob_reconciliation_ids = vehicle.voyage_ids.rob_reconciliation_ids

    bunker_stock_location_id = fields.Many2one(
        'stock.location', string='Lokasi Stok Bunker', readonly=True, copy=False,
        help='Auto-create saat penerimaan bunker pertama kali dikonfirmasi (child dari '
             'lokasi "Vessels") — keputusan teknis Sprint 22, tidak ada konsep '
             'stock.location per kapal di modul fleet existing manapun.',
    )

    def _get_bunker_stock_location(self):
        """Lazy get-or-create — idempotent aman untuk demo data reload."""
        self.ensure_one()
        if self.bunker_stock_location_id:
            return self.bunker_stock_location_id
        parent = self.env.ref(
            'vessel_bunker_management.stock_location_vessels', raise_if_not_found=False,
        )
        location = self.env['stock.location'].search([
            ('name', '=', self.name), ('location_id', '=', parent.id if parent else False),
            ('usage', '=', 'internal'),
        ], limit=1)
        if not location:
            location = self.env['stock.location'].create({
                'name': self.name,
                'location_id': parent.id if parent else False,
                'usage': 'internal',
            })
        self.bunker_stock_location_id = location.id
        return location
