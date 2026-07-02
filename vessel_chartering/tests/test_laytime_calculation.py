# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLaytimeCalculation(TransactionCase):
    """Unit test compute laytime — acceptance criteria §10.3/10.4 TECH_SPEC_vessel_chartering.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rain_type = cls.env['vessel.laytime.interruption.type'].create({
            'name': 'Test Rain',
            'is_counting': False,
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Test Charterer'})
        brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Test Brand'})
        model = cls.env['fleet.vehicle.model'].create({
            'name': 'Test Vessel Model', 'brand_id': brand.id,
        })
        vessel_type = cls.env['fleet.document.vessel.type'].create({'name': 'Test Type'})
        cls.vessel = cls.env['fleet.vehicle'].create({
            'model_id': model.id,
            'vessel_type_id': vessel_type.id,
            'license_plate': 'TEST-LAYTIME-01',
        })
        cls.contract = cls.env['vessel.charter.contract'].create({
            'contract_type': 'voyage',
            'direction': 'out',
            'partner_id': cls.partner.id,
            'vessel_id': cls.vessel.id,
            'demurrage_rate': 10000,
            'despatch_rate': 5000,
        })
        cls.base = datetime(2026, 1, 1, 8, 0, 0)
        # env.user default TransactionCase tidak otomatis anggota group custom —
        # tambahkan eksplisit supaya action_approve() (manager-only) bisa dites.
        cls.env.user.group_ids = [(4, cls.env.ref('vessel_chartering.group_chartering_manager').id)]

    def _create_laytime(self, allowed_hours):
        return self.env['vessel.laytime.calculation'].create({
            'contract_id': self.contract.id,
            'port_call_type': 'load',
            'laytime_allowed_hours': allowed_hours,
        })

    def _add_sof(self, laytime, start_offset_h, end_offset_h, interruption_type=None):
        self.env['vessel.sof.line'].create({
            'laytime_id': laytime.id,
            'datetime_start': self.base + timedelta(hours=start_offset_h),
            'datetime_end': self.base + timedelta(hours=end_offset_h),
            'interruption_type_id': interruption_type.id if interruption_type else False,
        })

    def test_01_no_interruption(self):
        """SOF tanpa interupsi — laytime_used = durasi total, balance & demurrage benar."""
        laytime = self._create_laytime(allowed_hours=48)
        self._add_sof(laytime, 0, 60)  # 60 jam counting normal, tanpa interupsi

        self.assertEqual(laytime.laytime_used_hours, 60)
        self.assertEqual(laytime.balance_hours, -12)  # 48 - 60
        self.assertEqual(laytime.time_on_demurrage_hours, 12)
        self.assertAlmostEqual(laytime.demurrage_amount, (12 / 24.0) * 10000)  # 5000
        self.assertEqual(laytime.despatch_amount, 0.0)

    def test_02_interruption_before_on_demurrage_excluded(self):
        """Interupsi non-counting SEBELUM titik on-demurrage → dikecualikan dari laytime_used."""
        laytime = self._create_laytime(allowed_hours=48)
        self._add_sof(laytime, 0, 40)                              # 40h counting
        self._add_sof(laytime, 40, 46, interruption_type=self.rain_type)  # 6h rain, excluded
        self._add_sof(laytime, 46, 50)                              # 4h counting

        # Total elapsed = 50h, tapi 6h rain dikecualikan (belum on-demurrage saat itu)
        self.assertEqual(laytime.laytime_used_hours, 44)  # 40 + 4, bukan 50
        self.assertEqual(laytime.balance_hours, 4)  # 48 - 44, positif (despatch)
        self.assertEqual(laytime.time_on_demurrage_hours, 0.0)
        self.assertEqual(laytime.demurrage_amount, 0.0)
        self.assertAlmostEqual(laytime.despatch_amount, (4 / 24.0) * 5000, places=2)

    def test_03_once_on_demurrage_always_on_demurrage(self):
        """
        Interupsi non-counting SETELAH titik on-demurrage tercapai → tetap dihitung
        (aturan "once on demurrage, always on demurrage"). Replikasi persis
        acceptance criteria §10.4 tech spec: balance -36 jam, rate USD 10,000/day
        → demurrage_amount = USD 15,000.
        """
        laytime = self._create_laytime(allowed_hours=96)
        self._add_sof(laytime, 0, 72)                                # 72h counting
        self._add_sof(laytime, 72, 78, interruption_type=self.rain_type)   # 6h rain, SEBELUM threshold → excluded
        self._add_sof(laytime, 78, 96)                                # 18h counting -> counting_total=90
        self._add_sof(laytime, 96, 102)                               # 6h counting -> counting_total=96, ON DEMURRAGE tercapai
        self._add_sof(laytime, 102, 108, interruption_type=self.rain_type)  # 6h rain, SUDAH on-demurrage → tetap counting
        self._add_sof(laytime, 108, 138)                              # 30h counting (sudah on-demurrage)

        # used = 72 + 18 + 6 + 6 + 30 = 132 (6h rain pertama dikecualikan, rain kedua TIDAK)
        self.assertEqual(laytime.laytime_used_hours, 132)
        self.assertEqual(laytime.balance_hours, -36)  # 96 - 132
        self.assertEqual(laytime.time_on_demurrage_hours, 36)
        self.assertAlmostEqual(laytime.demurrage_amount, 15000.0)  # (36/24) * 10000 — acceptance criteria §10.4
        self.assertEqual(laytime.despatch_amount, 0.0)

    def test_04_contract_aggregation_non_reversible(self):
        """demurrage_amount_total di kontrak — agregasi sum langsung (non-reversible)."""
        laytime = self._create_laytime(allowed_hours=96)
        self._add_sof(laytime, 0, 132)  # langsung 132h counting, tanpa interupsi
        laytime.state = 'submitted'
        laytime.action_approve()

        self.assertEqual(laytime.demurrage_amount, 15000.0)
        self.assertEqual(self.contract.demurrage_amount_total, 15000.0)
        self.assertEqual(self.contract.despatch_amount_total, 0.0)
