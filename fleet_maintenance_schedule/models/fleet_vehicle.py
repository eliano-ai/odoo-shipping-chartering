# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    maintenance_schedule_ids = fields.One2many(
        'fleet.maintenance.schedule',
        'vehicle_id',
        string='Maintenance Schedules',
        copy=False,
    )
    maintenance_schedule_count = fields.Integer(
        string='Maintenance Schedules',
        compute='_compute_maintenance_schedule_count',
    )
    maintenance_schedule_due_count = fields.Integer(
        string='Overdue / Due Soon',
        compute='_compute_maintenance_schedule_count',
    )

    @api.depends('maintenance_schedule_ids', 'maintenance_schedule_ids.state')
    def _compute_maintenance_schedule_count(self):
        from datetime import date, timedelta
        today = date.today()
        soon = today + timedelta(days=7)
        for vehicle in self:
            schedules = vehicle.maintenance_schedule_ids
            vehicle.maintenance_schedule_count = len(schedules)
            vehicle.maintenance_schedule_due_count = len(schedules.filtered(
                lambda s: s.state in ('draft', 'confirmed', 'in_progress')
                and s.scheduled_date
                and s.scheduled_date <= soon
            ))

    def action_view_maintenance_schedules(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Maintenance Schedules — %s') % self.name,
            'res_model': 'fleet.maintenance.schedule',
            'view_mode': 'list,form,calendar',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {
                'default_vehicle_id': self.id,
                'search_default_vehicle_id': self.id,
            },
            'target': 'current',
        }
