# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FleetVehicleTrip(models.Model):
    _name = 'fleet.vehicle.trip'
    _description = 'Fleet Vehicle Trip / Voyage'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'departure_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Trip / Voyage Name',
        required=True,
        tracking=True,
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    driver_id = fields.Many2one(
        'res.partner',
        string='Driver / Captain',
        related='vehicle_id.driver_id',
        readonly=True,
        store=True,
    )
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
    )

    # ─── Schedule ────────────────────────────────────────────────────────────
    departure_date = fields.Datetime(
        string='Departure',
        required=True,
        tracking=True,
    )
    arrival_date = fields.Datetime(
        string='Arrival',
        tracking=True,
    )
    departure_port = fields.Char(string='From (Port / Location)')
    arrival_port = fields.Char(string='To (Port / Location)')

    # ─── Odometer ────────────────────────────────────────────────────────────
    odometer_start = fields.Float(string='Odometer / Meter Start', digits=(10, 2))
    odometer_end = fields.Float(string='Odometer / Meter End', digits=(10, 2))
    distance_km = fields.Float(
        string='Distance (km / nm)',
        compute='_compute_distance',
        store=True,
        digits=(10, 2),
    )

    # ─── Fuel Logs ───────────────────────────────────────────────────────────
    fuel_log_ids = fields.One2many(
        'fleet.fuel.log',
        'trip_id',
        string='Fuel Logs',
    )
    fuel_log_count = fields.Integer(
        string='Fuel Logs',
        compute='_compute_fuel_stats',
    )
    total_fuel_qty = fields.Float(
        string='Total Fuel (L)',
        compute='_compute_fuel_stats',
        store=True,
        digits=(10, 3),
    )
    total_fuel_cost = fields.Monetary(
        string='Total Fuel Cost',
        compute='_compute_fuel_stats',
        store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )
    avg_consumption = fields.Float(
        string='Avg Consumption (L/100km)',
        compute='_compute_fuel_stats',
        store=True,
        digits=(10, 3),
    )

    # ─── State ───────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('planned', 'Planned'),
            ('ongoing', 'Ongoing'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='planned',
        readonly=True,
        tracking=True,
        copy=False,
    )
    note = fields.Text(string='Notes')

    # ─── Computed ────────────────────────────────────────────────────────────
    @api.depends('odometer_start', 'odometer_end')
    def _compute_distance(self):
        for rec in self:
            rec.distance_km = max(0.0, (rec.odometer_end or 0.0) - (rec.odometer_start or 0.0))

    @api.depends('fuel_log_ids', 'fuel_log_ids.qty_liters', 'fuel_log_ids.total_cost', 'fuel_log_ids.state')
    def _compute_fuel_stats(self):
        for rec in self:
            approved_logs = rec.fuel_log_ids.filtered(
                lambda l: l.state in ('approved', 'posted')
            )
            rec.fuel_log_count = len(rec.fuel_log_ids)
            rec.total_fuel_qty = sum(approved_logs.mapped('qty_liters'))
            rec.total_fuel_cost = sum(approved_logs.mapped('total_cost'))
            if rec.distance_km and rec.distance_km > 0 and rec.total_fuel_qty:
                rec.avg_consumption = (rec.total_fuel_qty / rec.distance_km) * 100.0
            else:
                rec.avg_consumption = 0.0

    # ─── State Actions ───────────────────────────────────────────────────────
    def action_start(self):
        for rec in self:
            if rec.state != 'planned':
                raise UserError(_('Only Planned trips can be started.'))
            rec.state = 'ongoing'

    def action_done(self):
        for rec in self:
            if rec.state != 'ongoing':
                raise UserError(_('Only Ongoing trips can be completed.'))
            rec.state = 'done'

    def action_cancel(self):
        for rec in self:
            if rec.state == 'done':
                raise UserError(_('Cannot cancel a completed trip.'))
            rec.state = 'cancelled'

    def action_reset(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_('Only cancelled trips can be reset.'))
            rec.state = 'planned'

    def action_view_fuel_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fuel Logs — %s') % self.name,
            'res_model': 'fleet.fuel.log',
            'view_mode': 'list,form',
            'domain': [('trip_id', '=', self.id)],
            'context': {'default_trip_id': self.id, 'default_vehicle_id': self.vehicle_id.id},
        }
