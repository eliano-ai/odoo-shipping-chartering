# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FleetVehicleVoyageOperations(models.Model):
    _inherit = 'fleet.vehicle'

    voyage_ids = fields.One2many(
        'vessel.voyage', 'vessel_id', string='Riwayat Voyage',
    )
    current_voyage_id = fields.Many2one(
        'vessel.voyage', string='Voyage Berjalan',
        compute='_compute_current_voyage_id', store=True,
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

    @api.depends(
        'current_voyage_id', 'current_voyage_id.noon_report_ids.state',
        'current_voyage_id.noon_report_ids.latitude', 'current_voyage_id.noon_report_ids.longitude',
    )
    def _compute_current_position(self):
        for vehicle in self:
            voyage = vehicle.current_voyage_id
            last_report = voyage.noon_report_ids.filtered(
                lambda r: r.state == 'approved'
            ).sorted('report_datetime', reverse=True)[:1] if voyage else self.env['vessel.noon.report']
            vehicle.current_position_lat = last_report.latitude or 0.0
            vehicle.current_position_lng = last_report.longitude or 0.0
