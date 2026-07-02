# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHireStatement(TransactionCase):
    """Unit test hire statement & off-hire — acceptance criteria §10.6 TECH_SPEC_vessel_chartering.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Test TC Charterer'})
        brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Test TC Brand'})
        model = cls.env['fleet.vehicle.model'].create({
            'name': 'Test TC Vessel Model', 'brand_id': brand.id,
        })
        vessel_type = cls.env['fleet.document.vessel.type'].create({'name': 'Test TC Type'})
        cls.vessel = cls.env['fleet.vehicle'].create({
            'model_id': model.id,
            'vessel_type_id': vessel_type.id,
            'license_plate': 'TEST-TC-01',
        })
        cls.contract = cls.env['vessel.charter.contract'].create({
            'contract_type': 'time',
            'direction': 'out',
            'partner_id': cls.partner.id,
            'vessel_id': cls.vessel.id,
            'hire_rate': 8000,
            'hire_payment_term': '15_days_advance',
        })

    def test_01_net_hire_days_with_full_offhire(self):
        """Hire statement 15 hari, off-hire 12 jam penuh dalam periode → net_hire_days = 14.5."""
        period_start = datetime(2026, 1, 1).date()
        period_end = period_start + timedelta(days=15)
        line = self.env['vessel.hire.statement.line'].create({
            'contract_id': self.contract.id,
            'period_start': period_start,
            'period_end': period_end,
        })
        self.env['vessel.offhire.event'].create({
            'contract_id': self.contract.id,
            'datetime_start': datetime(2026, 1, 5, 6, 0, 0),
            'datetime_end': datetime(2026, 1, 5, 18, 0, 0),  # 12 jam, full di dalam periode
            'reason': 'breakdown',
        })

        self.assertEqual(line.days_in_period, 15)
        self.assertEqual(line.offhire_hours, 12)
        self.assertEqual(line.net_hire_days, 14.5)  # 15 - 12/24 — persis acceptance criteria §10.6
        self.assertAlmostEqual(line.hire_amount, 14.5 * 8000, places=2)

    def test_02_offhire_partial_overlap_proportional(self):
        """Off-hire yang overlap SEBAGIAN dengan periode → hanya porsi overlap yang dihitung."""
        period_start = datetime(2026, 2, 1).date()
        period_end = period_start + timedelta(days=15)
        line = self.env['vessel.hire.statement.line'].create({
            'contract_id': self.contract.id,
            'period_start': period_start,
            'period_end': period_end,
        })
        # Event mulai SEBELUM periode (31 Jan 18:00) dan berakhir SETELAH periode dimulai
        # (1 Feb 06:00) — durasi event 12 jam, tapi overlap dengan periode cuma 6 jam.
        self.env['vessel.offhire.event'].create({
            'contract_id': self.contract.id,
            'datetime_start': datetime(2026, 1, 31, 18, 0, 0),
            'datetime_end': datetime(2026, 2, 1, 6, 0, 0),
            'reason': 'crew',
        })

        self.assertEqual(line.offhire_hours, 6)  # bukan 12 — cuma porsi yang overlap
        self.assertEqual(line.net_hire_days, 15 - 6 / 24.0)

    def test_03_generate_hire_statement_no_duplicate(self):
        """action_generate_hire_statement membuat periode berurutan, tolak duplikat."""
        self.contract.write({
            'delivery_date': datetime(2026, 3, 1, 8, 0, 0),
        })
        action1 = self.contract.action_generate_hire_statement()
        line1 = self.env['vessel.hire.statement.line'].browse(action1['res_id'])
        self.assertEqual(line1.period_start, datetime(2026, 3, 1).date())
        self.assertEqual(line1.period_end, datetime(2026, 3, 16).date())  # +15 hari

        action2 = self.contract.action_generate_hire_statement()
        line2 = self.env['vessel.hire.statement.line'].browse(action2['res_id'])
        self.assertEqual(line2.period_start, line1.period_end)  # lanjut dari periode sebelumnya

        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.env['vessel.hire.statement.line'].create({
                'contract_id': self.contract.id,
                'period_start': line1.period_start,
                'period_end': line1.period_end,
            })
