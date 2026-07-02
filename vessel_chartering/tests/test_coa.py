# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCoa(TransactionCase):
    """Unit test COA — acceptance criteria §10.8 TECH_SPEC_vessel_chartering.md
    (COA dengan 3 shipment child → qty_remaining terhitung benar)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Test COA Charterer'})
        brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Test COA Brand'})
        model = cls.env['fleet.vehicle.model'].create({
            'name': 'Test COA Vessel Model', 'brand_id': brand.id,
        })
        vessel_type = cls.env['fleet.document.vessel.type'].create({'name': 'Test COA Type'})
        cls.vessel = cls.env['fleet.vehicle'].create({
            'model_id': model.id,
            'vessel_type_id': vessel_type.id,
            'license_plate': 'TEST-COA-01',
        })

    def test_01_coa_qty_remaining_three_shipments(self):
        coa = self.env['vessel.charter.contract'].create({
            'contract_type': 'coa',
            'direction': 'out',
            'partner_id': self.partner.id,
            'total_qty_commitment': 100000,
        })
        shipments = self.env['vessel.charter.contract']
        for i, qty in enumerate((6000, 7000, 5500), start=1):
            shipments |= self.env['vessel.charter.contract'].create({
                'contract_type': 'voyage',
                'direction': 'out',
                'coa_id': coa.id,
                'partner_id': self.partner.id,
                'vessel_id': self.vessel.id,
                'cargo_qty': qty,
                'bl_qty': qty,
                'freight_basis': 'per_mt',
                'freight_rate': 11.0,
                'state': 'completed',
            })

        self.assertEqual(len(coa.shipment_ids), 3)
        self.assertEqual(coa.qty_shipped, 18500)  # 6000+7000+5500
        self.assertEqual(coa.qty_remaining, 100000 - 18500)

        # Shipment yang masih draft TIDAK ikut dihitung sebagai qty_shipped
        self.env['vessel.charter.contract'].create({
            'contract_type': 'voyage',
            'direction': 'out',
            'coa_id': coa.id,
            'partner_id': self.partner.id,
            'vessel_id': self.vessel.id,
            'cargo_qty': 9999,
            'bl_qty': 9999,
        })
        self.assertEqual(coa.qty_shipped, 18500)  # tidak berubah, shipment ke-4 masih draft
