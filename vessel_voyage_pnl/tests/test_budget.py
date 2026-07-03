# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBudget(TransactionCase):

    def test_calc_variance_matches_acceptance_criteria(self):
        """§10.8 acceptance criteria persis: planned 50,000, actual 65,000 -> variance_pct 30%."""
        Line = self.env['vessel.vessel.budget.line']
        variance_amount, variance_pct = Line._calc_variance(50000, 65000)
        self.assertEqual(variance_amount, 15000.0)
        self.assertEqual(variance_pct, 30.0)

    def test_calc_variance_zero_planned(self):
        Line = self.env['vessel.vessel.budget.line']
        variance_amount, variance_pct = Line._calc_variance(0, 5000)
        self.assertEqual(variance_amount, 5000.0)
        self.assertEqual(variance_pct, 0.0)

    def test_group_voyage_pnl_user_denied_budget_access(self):
        """§10.9 acceptance criteria — group_voyage_pnl_user TIDAK bisa akses Budget
        sama sekali (bukan cuma tidak ada tombol, tapi benar-benar AccessError)."""
        test_user = self.env['res.users'].create({
            'name': 'Test Voyage Ops User',
            'login': 'test_voyage_pnl_user_budget',
            'group_ids': [(6, 0, [
                self.env.ref('vessel_voyage_pnl.group_voyage_pnl_user').id,
                self.env.ref('base.group_user').id,
            ])],
        })
        with self.assertRaises(AccessError):
            self.env['vessel.vessel.budget'].with_user(test_user).search([])
