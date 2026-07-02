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

    # charter_contract_ids, active_charter_id, charter_status sengaja BELUM
    # ditambahkan di sprint ini — target model vessel.charter.contract baru
    # dibuat Sprint 2. Menambahkan One2many ke model yang belum ada akan
    # membuat registry gagal load. Field ini dipindah ke Sprint 2.

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
