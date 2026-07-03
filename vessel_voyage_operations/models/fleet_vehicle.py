# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FleetVehicleVoyageOperations(models.Model):
    _inherit = 'fleet.vehicle'

    voyage_ids = fields.One2many(
        'vessel.voyage', 'vessel_id', string='Riwayat Voyage',
    )
    current_voyage_id = fields.Many2one(
        'vessel.voyage', string='Voyage Berjalan',
        compute='_compute_current_voyage_id',
    )
    current_position_lat = fields.Float(
        string='Posisi Terkini — Latitude', compute='_compute_current_position',
        digits=(10, 6),
    )
    current_position_lng = fields.Float(
        string='Posisi Terkini — Longitude', compute='_compute_current_position',
        digits=(10, 6),
    )

    @api.depends('voyage_ids', 'voyage_ids.state')
    def _compute_current_voyage_id(self):
        for vehicle in self:
            active = vehicle.voyage_ids.filtered(
                lambda v: v.state in ('sailing', 'at_port')
            )[:1]
            vehicle.current_voyage_id = active

    @api.depends('current_voyage_id')
    def _compute_current_position(self):
        # Placeholder — akan diisi dari noon_report_ids approved terakhir
        # setelah vessel.noon.report ada (Sprint 11).
        for vehicle in self:
            vehicle.current_position_lat = 0.0
            vehicle.current_position_lng = 0.0
