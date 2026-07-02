# -*- coding: utf-8 -*-
from odoo import fields, models


class FleetFuelType(models.Model):
    _name = 'fleet.fuel.type'
    _description = 'Fleet Fuel Type'
    _order = 'sequence, name'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Fuel Type', required=True, translate=True)
    code = fields.Char(string='Code', size=10)
    active = fields.Boolean(default=True)

    product_id = fields.Many2one(
        'product.product',
        string='Inventory Product',
        domain="[('type', 'in', ['product', 'consu'])]",
        help='Produk BBM di Inventory. Dipakai untuk membuat stock.move saat Approved.',
    )
    account_id = fields.Many2one(
        'account.account',
        string='Expense Account',
        domain="[('account_type', 'in', ['expense', 'direct_cost'])]",
        help='Akun beban BBM untuk journal entry saat Posted.',
    )

    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        help='Satuan volume (Liter, dll.)',
    )

    default_price = fields.Float(
        string='Default Price / Unit',
        digits='Product Price',
    )
    anomaly_threshold_pct = fields.Float(
        string='Anomaly Threshold (%)',
        default=30.0,
        help='Jika konsumsi L/100km melebihi rata-rata kendaraan × threshold ini, tandai sebagai anomali.',
    )
    color = fields.Integer(string='Color Index')
    note = fields.Text(string='Notes')

    fuel_log_count = fields.Integer(
        string='Fuel Logs',
        compute='_compute_fuel_log_count',
    )

    def _compute_fuel_log_count(self):
        FuelLog = self.env['fleet.fuel.log']
        for rec in self:
            rec.fuel_log_count = FuelLog.search_count([('fuel_type_id', '=', rec.id)])