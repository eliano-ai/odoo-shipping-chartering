# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAllocation(TransactionCase):
    """§12.4 tech spec — minimal 3 test case dengan angka BEDA membuktikan formula
    alokasi benar secara matematis, bukan cuma 'tidak error'."""

    def setUp(self):
        super().setUp()
        self.Pnl = self.env['vessel.voyage.pnl']

    def test_allocate_per_voyage_day(self):
        """§10.4 acceptance criteria persis: pool 30,000, voyage 10/30 hari -> 10,000."""
        amount = self.Pnl._allocate_per_voyage_day(30000, 10, 30)
        self.assertEqual(amount, 10000.0)

    def test_allocate_per_voyage_day_zero_total_active_days(self):
        amount = self.Pnl._allocate_per_voyage_day(30000, 10, 0)
        self.assertEqual(amount, 0.0)

    def test_allocate_equal_split(self):
        amount = self.Pnl._allocate_equal_split(9000, 3)
        self.assertEqual(amount, 3000.0)

    def test_allocate_equal_split_zero_voyages(self):
        amount = self.Pnl._allocate_equal_split(9000, 0)
        self.assertEqual(amount, 0.0)

    def test_allocate_fixed_percentage(self):
        amount = self.Pnl._allocate_fixed_percentage(5.0, 100000)
        self.assertEqual(amount, 5000.0)

    def test_allocate_manual_always_zero(self):
        amount = self.Pnl._allocate_manual()
        self.assertEqual(amount, 0.0)
