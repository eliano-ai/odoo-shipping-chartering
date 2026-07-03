# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestVoyageDelayCargo(TransactionCase):
    """Unit test vessel.voyage.delay compute & record rule portal Nakhoda —
    acceptance criteria §10.4 tech spec."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Test Charterer DC'})
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Test Brand DC'})
        cls.model = cls.env['fleet.vehicle.model'].create({
            'name': 'Test Vessel Model DC', 'brand_id': cls.brand.id,
        })
        cls.vessel_type = cls.env['fleet.document.vessel.type'].create({'name': 'Test Type DC'})

    def _create_voyage(self, license_plate):
        vessel = self.env['fleet.vehicle'].create({
            'model_id': self.model.id,
            'vessel_type_id': self.vessel_type.id,
            'license_plate': license_plate,
        })
        contract = self.env['vessel.charter.contract'].create({
            'contract_type': 'voyage',
            'direction': 'out',
            'partner_id': self.partner.id,
            'vessel_id': vessel.id,
            'date_start': '2026-01-01',
            'freight_rate': 10.0,
            'cargo_qty': 5000,
        })
        contract.action_confirm()
        voyage = self.env['vessel.voyage'].create({'charter_contract_id': contract.id})
        return vessel, voyage

    def test_01_duration_hours_compute(self):
        vessel, voyage = self._create_voyage('TEST-DELAY-01')
        delay_type = self.env['vessel.delay.type'].search([], limit=1)
        base = datetime(2026, 2, 1, 6, 0, 0)
        delay = self.env['vessel.voyage.delay'].create({
            'voyage_id': voyage.id,
            'delay_type_id': delay_type.id,
            'datetime_start': base,
            'datetime_end': base + timedelta(hours=5, minutes=30),
        })
        self.assertAlmostEqual(delay.duration_hours, 5.5, places=2)
        self.assertAlmostEqual(voyage.total_delay_hours, 5.5, places=2)

    def test_02_portal_record_rule_isolation(self):
        """Nakhoda A (on_board kapal A) tidak boleh lihat voyage kapal B (Nakhoda B)."""
        portal_group = self.env.ref('vessel_voyage_operations.group_voyage_ops_portal')
        base_portal_group = self.env.ref('base.group_portal')
        rank = self.env['vessel.crew.rank'].search([], limit=1) or self.env['vessel.crew.rank'].create({
            'name': 'Test Rank DC',
        })

        vessel_a, voyage_a = self._create_voyage('TEST-DELAY-A')
        vessel_b, voyage_b = self._create_voyage('TEST-DELAY-B')

        user_a = self.env['res.users'].create({
            'name': 'Nakhoda A', 'login': 'nakhoda_a_test@example.com',
            'group_ids': [(6, 0, [portal_group.id, base_portal_group.id])],
        })
        user_b = self.env['res.users'].create({
            'name': 'Nakhoda B', 'login': 'nakhoda_b_test@example.com',
            'group_ids': [(6, 0, [portal_group.id, base_portal_group.id])],
        })
        employee_a = self.env['hr.employee'].create({'name': 'Nakhoda A', 'user_id': user_a.id})
        employee_b = self.env['hr.employee'].create({'name': 'Nakhoda B', 'user_id': user_b.id})
        seafarer_a = self.env['vessel.seafarer'].create({'employee_id': employee_a.id})
        seafarer_b = self.env['vessel.seafarer'].create({'employee_id': employee_b.id})

        self.env['vessel.crew.assignment'].create({
            'vehicle_id': vessel_a.id, 'seafarer_id': seafarer_a.id, 'rank_id': rank.id,
            'sign_on_date': '2026-01-01', 'state': 'on_board',
        })
        self.env['vessel.crew.assignment'].create({
            'vehicle_id': vessel_b.id, 'seafarer_id': seafarer_b.id, 'rank_id': rank.id,
            'sign_on_date': '2026-01-01', 'state': 'on_board',
        })

        self.assertIn(user_a, voyage_a.assigned_user_ids)
        self.assertNotIn(user_b, voyage_a.assigned_user_ids)

        voyages_visible_to_a = self.env['vessel.voyage'].with_user(user_a).search([])
        self.assertIn(voyage_a.id, voyages_visible_to_a.ids)
        self.assertNotIn(voyage_b.id, voyages_visible_to_a.ids)
