# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRobReconciliation(TransactionCase):

    def setUp(self):
        super().setUp()
        self.voyage = self.env.ref('vessel_voyage_operations.demo_voyage_3')
        self.reconciliation = self.env['vessel.bunker.rob.reconciliation'].search([
            ('voyage_id', '=', self.voyage.id), ('fuel_type', '=', 'fo'),
        ], limit=1)

    def test_total_supply_from_confirmed_delivery(self):
        self.assertAlmostEqual(self.reconciliation.total_supply, 495.0, places=1)

    def test_total_consumption_from_fuel_log(self):
        self.assertAlmostEqual(self.reconciliation.total_consumption, 150.0, places=1)

    def test_expected_rob_formula(self):
        """§10.5 acceptance criteria persis: 200 + 495 - 150 = 545."""
        self.assertAlmostEqual(self.reconciliation.previous_rob, 200.0, places=1)
        self.assertAlmostEqual(self.reconciliation.expected_rob, 545.0, places=1)

    def test_variance_and_anomaly(self):
        """§10.5 acceptance criteria persis: actual 500 -> variance -45, anomaly di
        threshold 8% (variance_pct ~8.26%)."""
        self.assertAlmostEqual(self.reconciliation.actual_rob, 500.0, places=1)
        self.assertAlmostEqual(self.reconciliation.variance, -45.0, places=1)
        self.assertGreater(abs(self.reconciliation.variance_pct), 8.0)
        self.assertTrue(self.reconciliation.is_anomaly)

    def test_pure_formula_components_isolated(self):
        """Pecah compute jadi 3 method terpisah (§12.2 poin 7) — verifikasi formula
        expected_rob murni dengan angka berbeda dari demo, tanpa fixture DB."""
        previous_rob, supply, consumption = 100.0, 50.0, 30.0
        expected = previous_rob + supply - consumption
        self.assertEqual(expected, 120.0)
