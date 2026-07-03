# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPnlCore(TransactionCase):
    """§10.5/§10.7/§10.10 acceptance criteria — compute inti (total_revenue,
    voyage_result, tce_actual_per_day, utilization_pct, estimate variance)
    diverifikasi dengan data demo nyata yang sudah di-generate (§10.2-§10.4)."""

    def setUp(self):
        super().setUp()
        self.voyage3 = self.env.ref('vessel_voyage_operations.demo_voyage_3')
        self.pnl = self.env['vessel.voyage.pnl'].search([('voyage_id', '=', self.voyage3.id)])

    def test_total_revenue_formula(self):
        self.assertTrue(self.pnl, 'Demo P&L voyage_3 harus sudah ter-generate.')
        expected = (
            self.pnl.freight_revenue + self.pnl.demurrage_revenue
            - self.pnl.despatch_cost - self.pnl.brokerage_cost + self.pnl.other_revenue
        )
        self.assertAlmostEqual(self.pnl.total_revenue, expected, places=2)
        self.assertAlmostEqual(self.pnl.total_revenue, 75275.0, places=2)

    def test_voyage_result_and_tce_exclude_allocated_cost(self):
        expected_result = (
            self.pnl.total_revenue - self.pnl.total_direct_cost - self.pnl.total_allocated_cost
        )
        self.assertAlmostEqual(self.pnl.voyage_result, expected_result, places=2)
        expected_tce = (
            (self.pnl.total_revenue - self.pnl.total_direct_cost) / self.pnl.voyage_days
        )
        self.assertAlmostEqual(self.pnl.tce_actual_per_day, expected_tce, places=2)

    def test_estimate_variance_computed_correctly(self):
        """§10.5 — voyage dengan estimate selected -> revenue/cost/tce variance benar."""
        contract = self.pnl.contract_id
        contract.freight_amount_estimate = 70000.0
        estimate = self.env['vessel.voyage.estimate'].create({
            'contract_id': contract.id,
            'name': 'Test Estimate',
            'speed_knots': 10,
            'port_days_discharge': 10,
            'port_cost_estimate': 5000,
            'state': 'selected',
        })
        self.pnl.estimate_id = estimate.id
        self.pnl._compute_estimate_variance()

        self.assertAlmostEqual(
            self.pnl.revenue_variance, self.pnl.total_revenue - estimate.revenue_estimate, places=2,
        )
        self.assertAlmostEqual(
            self.pnl.revenue_variance_pct,
            (self.pnl.revenue_variance / estimate.revenue_estimate) * 100.0, places=2,
        )
        self.assertAlmostEqual(
            self.pnl.tce_variance, self.pnl.tce_actual_per_day - estimate.tce_per_day, places=2,
        )

    def test_utilization_pct_matches_voyage_days_vs_calendar_days(self):
        """§10.7 — utilization_pct = voyage_days_total / calendar_days x 100."""
        vessel_pnl = self.env['vessel.vessel.pnl'].search([
            ('vessel_id', '=', self.pnl.vessel_id.id),
            ('period_month', '=', str(self.voyage3.date_departure.month)),
            ('period_year', '=', self.voyage3.date_departure.year),
        ])
        self.assertTrue(vessel_pnl, 'Demo vessel.vessel.pnl bulan voyage_3 harus sudah ada.')
        expected = (vessel_pnl.voyage_days_total / vessel_pnl.calendar_days) * 100.0
        self.assertAlmostEqual(vessel_pnl.utilization_pct, expected, places=2)

    def test_group_voyage_pnl_user_cannot_generate_or_lock_pnl(self):
        """§10.9 — group_voyage_pnl_user tidak bisa generate/lock P&L (create/write denied)."""
        test_user = self.env['res.users'].create({
            'name': 'Test Voyage Ops User 2',
            'login': 'test_voyage_pnl_user_generate',
            'group_ids': [(6, 0, [
                self.env.ref('vessel_voyage_pnl.group_voyage_pnl_user').id,
                self.env.ref('base.group_user').id,
            ])],
        })
        with self.assertRaises(AccessError):
            self.env['vessel.voyage.pnl'].with_user(test_user).create({
                'voyage_id': self.voyage3.id,
            })
        with self.assertRaises(AccessError):
            self.pnl.with_user(test_user).write({'state': 'locked'})
