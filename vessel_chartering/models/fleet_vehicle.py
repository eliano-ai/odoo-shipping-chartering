# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FleetVehicleChartering(models.Model):
    _inherit = 'fleet.vehicle'

    # gt/dwt sudah tersedia sebagai gross_tonnage/deadweight_tonnage dari
    # fleet_document_id — sengaja tidak dibuat field baru untuk hindari duplikasi.

    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account (Vessel)',
        readonly=True, copy=False,
        help='Analytic account di plan Vessel — auto-dibuat saat kapal ditandai is_vessel.',
    )

    charter_contract_ids = fields.One2many(
        'vessel.charter.contract', 'vessel_id',
        string='Riwayat Penugasan Charter',
    )
    active_charter_id = fields.Many2one(
        'vessel.charter.contract', string='Kontrak Aktif',
        compute='_compute_charter_status',
    )
    charter_status = fields.Selection(
        [
            ('available', 'Tersedia'),
            ('on_voyage_charter', 'Voyage Charter Aktif'),
            ('on_time_charter', 'Time Charter Aktif'),
            ('chartered_in', 'Charter-In Aktif'),
        ],
        string='Status Charter', compute='_compute_charter_status',
    )

    @api.depends('charter_contract_ids', 'charter_contract_ids.state',
                 'charter_contract_ids.contract_type', 'charter_contract_ids.direction')
    def _compute_charter_status(self):
        for vehicle in self:
            active = vehicle.charter_contract_ids.filtered(
                lambda c: c.state == 'in_progress'
            )[:1]
            vehicle.active_charter_id = active
            if not active:
                vehicle.charter_status = 'available'
            elif active.direction == 'in':
                vehicle.charter_status = 'chartered_in'
            elif active.contract_type == 'time':
                vehicle.charter_status = 'on_time_charter'
            else:
                vehicle.charter_status = 'on_voyage_charter'

    @api.model_create_multi
    def create(self, vals_list):
        vehicles = super().create(vals_list)
        vehicles.filtered('is_vessel')._ensure_vessel_analytic_account()
        return vehicles

    def write(self, vals):
        res = super().write(vals)
        if vals.get('vessel_type_id'):
            self.filtered('is_vessel')._ensure_vessel_analytic_account()
        return res

    def _ensure_vessel_analytic_account(self):
        """Auto-create analytic account di plan Vessel untuk kapal yang belum punya."""
        plan = self.env.ref(
            'vessel_chartering.account_analytic_plan_vessel', raise_if_not_found=False,
        )
        if not plan:
            return
        for vehicle in self:
            if vehicle.analytic_account_id:
                continue
            account = self.env['account.analytic.account'].create({
                'name': vehicle.name or vehicle.license_plate,
                'plan_id': plan.id,
                'company_id': vehicle.company_id.id,
            })
            vehicle.analytic_account_id = account
