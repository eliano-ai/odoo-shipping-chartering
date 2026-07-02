# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    fuel_log_ids = fields.One2many(
        'fleet.fuel.log',
        'vehicle_id',
        string='Fuel Logs',
        copy=False,
    )
    trip_ids = fields.One2many(
        'fleet.vehicle.trip',
        'vehicle_id',
        string='Trips',
        copy=False,
    )

    # ─── Smart button counts ─────────────────────────────────────────────────
    fuel_log_count = fields.Integer(
        string='Fuel Logs',
        compute='_compute_fuel_stats',
    )
    total_fuel_cost_ytd = fields.Monetary(
        string='Fuel Cost (YTD)',
        compute='_compute_fuel_stats',
        currency_field='currency_id',
    )
    avg_consumption = fields.Float(
        string='Avg Consumption (L/100km)',
        compute='_compute_fuel_stats',
        digits=(10, 3),
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True,
    )
    trip_count = fields.Integer(
        string='Trips',
        compute='_compute_trip_count',
    )

    @api.depends('fuel_log_ids', 'fuel_log_ids.state', 'fuel_log_ids.total_cost',
                 'fuel_log_ids.consumption_rate', 'fuel_log_ids.date')
    def _compute_fuel_stats(self):
        from datetime import date
        ytd_start = date.today().replace(month=1, day=1)
        for vehicle in self:
            all_logs = vehicle.fuel_log_ids
            vehicle.fuel_log_count = len(all_logs)
            ytd_logs = all_logs.filtered(
                lambda l: l.state in ('approved', 'posted') and l.date and l.date >= ytd_start
            )
            vehicle.total_fuel_cost_ytd = sum(ytd_logs.mapped('total_cost'))
            rates = [l.consumption_rate for l in all_logs.filtered(
                lambda l: l.consumption_rate > 0 and l.state in ('approved', 'posted')
            )]
            vehicle.avg_consumption = sum(rates) / len(rates) if rates else 0.0

    @api.depends('trip_ids')
    def _compute_trip_count(self):
        for vehicle in self:
            vehicle.trip_count = len(vehicle.trip_ids)

    # ─── Smart button actions ─────────────────────────────────────────────────
    def action_view_fuel_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fuel Logs — %s') % self.name,
            'res_model': 'fleet.fuel.log',
            'view_mode': 'list,form,pivot',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id},
        }

    def action_view_trips(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Trips — %s') % self.name,
            'res_model': 'fleet.vehicle.trip',
            'view_mode': 'list,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id},
        }
