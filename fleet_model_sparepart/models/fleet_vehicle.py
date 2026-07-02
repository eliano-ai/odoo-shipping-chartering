# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    sparepart_ids = fields.One2many(
        'fleet.model.sparepart',
        'vehicle_id',
        string='Spareparts',
        copy=True,
    )
    sparepart_count = fields.Integer(
        string='Spareparts',
        compute='_compute_sparepart_count',
    )
    sparepart_total_value = fields.Monetary(
        string='Total Sparepart Value',
        compute='_compute_sparepart_count',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True,
    )

    @api.depends('sparepart_ids', 'sparepart_ids.subtotal')
    def _compute_sparepart_count(self):
        for vehicle in self:
            vehicle.sparepart_count = len(vehicle.sparepart_ids)
            vehicle.sparepart_total_value = sum(
                vehicle.sparepart_ids.mapped('subtotal')
            )

    def action_view_spareparts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Spareparts — %s') % self.name,
            'res_model': 'fleet.model.sparepart',
            'view_mode': 'list,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id},
        }
