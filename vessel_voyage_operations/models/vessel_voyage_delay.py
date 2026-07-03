# -*- coding: utf-8 -*-
from odoo import api, fields, models


class VesselVoyageDelay(models.Model):
    _name = 'vessel.voyage.delay'
    _description = 'Delay/Event Log Voyage'
    _order = 'voyage_id, datetime_start desc'

    voyage_id = fields.Many2one(
        'vessel.voyage', string='Voyage', required=True, ondelete='cascade',
    )
    port_call_id = fields.Many2one(
        'vessel.port.call', string='Port Call',
        help='Opsional — delay bisa terjadi di laut (bukan di port tertentu).',
    )
    delay_type_id = fields.Many2one('vessel.delay.type', string='Tipe Delay')
    vessel_id = fields.Many2one(
        'fleet.vehicle', string='Kapal',
        related='voyage_id.vessel_id', store=True, readonly=True,
    )
    datetime_start = fields.Datetime(string='Mulai')
    datetime_end = fields.Datetime(string='Selesai')
    duration_hours = fields.Float(
        string='Durasi (jam)', compute='_compute_duration_hours', store=True,
    )
    description = fields.Char(string='Deskripsi')
    impacts_laytime = fields.Boolean(
        string='Berdampak ke Laytime',
        help='Flag informasional — cross-check manual terhadap SOF di vessel_chartering. '
             'MVP: tidak otomatis sinkron (lihat §8 tech spec).',
    )
    company_id = fields.Many2one(
        related='voyage_id.company_id', string='Perusahaan', store=True, readonly=True,
    )

    @api.depends('datetime_start', 'datetime_end')
    def _compute_duration_hours(self):
        for rec in self:
            if rec.datetime_start and rec.datetime_end:
                delta = rec.datetime_end - rec.datetime_start
                rec.duration_hours = delta.total_seconds() / 3600.0
            else:
                rec.duration_hours = 0.0
