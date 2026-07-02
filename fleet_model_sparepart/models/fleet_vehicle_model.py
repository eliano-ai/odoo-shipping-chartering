# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class FleetVehicleModel(models.Model):
    _inherit = 'fleet.vehicle.model'

    # ─── Many2many: kapal-kapal yang menggunakan model ini ───────────────────
    # Sebenarnya fleet.vehicle sudah punya model_id (M2O ke fleet.vehicle.model),
    # sehingga kita bisa compute inverse-nya. Kita expose sebagai related O2M
    # computed agar bisa ditampilkan di tab tanpa menyimpan data redundan.
    vehicle_ids = fields.One2many(
        'fleet.vehicle',
        'model_id',
        string='Vehicles / Vessels',
        readonly=True,
    )
    vehicle_count = fields.Integer(
        string='Vehicles',
        compute='_compute_vehicle_stats',
    )
    sparepart_count = fields.Integer(
        string='Sparepartss',
        compute='_compute_vehicle_stats',
    )

    @api.depends('vehicle_ids', 'vehicle_ids.sparepart_ids')
    def _compute_vehicle_stats(self):
        for model in self:
            model.vehicle_count = len(model.vehicle_ids)
            model.sparepart_count = sum(
                len(v.sparepart_ids) for v in model.vehicle_ids
            )

    def action_view_vehicles(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vehicles — %s') % self.name,
            'res_model': 'fleet.vehicle',
            'view_mode': 'list,form',
            'domain': [('model_id', '=', self.id)],
            'context': {'default_model_id': self.id},
        }

    def action_view_spareparts(self):
        self.ensure_one()
        vehicle_ids = self.vehicle_ids.ids
        return {
            'type': 'ir.actions.act_window',
            'name': _('Spareparts — %s') % self.name,
            'res_model': 'fleet.model.sparepart',
            'view_mode': 'list,form',
            'domain': [('vehicle_id', 'in', vehicle_ids)],
            'context': {'default_vehicle_model_id': self.id},
        }
