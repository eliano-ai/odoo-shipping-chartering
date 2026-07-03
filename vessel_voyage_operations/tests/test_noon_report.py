# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestNoonReport(TransactionCase):
    """Unit test vessel.noon.report — acceptance criteria §10.5/10.6 tech spec."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        partner = cls.env['res.partner'].create({'name': 'Test Charterer NR'})
        brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Test Brand NR'})
        model = cls.env['fleet.vehicle.model'].create({
            'name': 'Test Vessel Model NR', 'brand_id': brand.id,
        })
        vessel_type = cls.env['fleet.document.vessel.type'].create({'name': 'Test Type NR'})
        vessel = cls.env['fleet.vehicle'].create({
            'model_id': model.id,
            'vessel_type_id': vessel_type.id,
            'license_plate': 'TEST-NOON-01',
        })
        contract = cls.env['vessel.charter.contract'].create({
            'contract_type': 'voyage',
            'direction': 'out',
            'partner_id': partner.id,
            'vessel_id': vessel.id,
            'date_start': '2026-01-01',
            'freight_rate': 10.0,
            'cargo_qty': 5000,
        })
        contract.action_confirm()
        cls.voyage = cls.env['vessel.voyage'].create({'charter_contract_id': contract.id})
        cls.base = datetime(2026, 1, 1, 12, 0, 0)

    def _create_report(self, offset_days, distance_run_nm=200.0, **extra):
        vals = {
            'voyage_id': self.voyage.id,
            'report_datetime': self.base + timedelta(days=offset_days),
            'distance_run_nm': distance_run_nm,
        }
        vals.update(extra)
        return self.env['vessel.noon.report'].create(vals)

    def test_01_total_distance_nm_from_approved_reports(self):
        """total_distance_nm voyage = sum distance_run_nm dari noon report approved saja."""
        r1 = self._create_report(0, distance_run_nm=220.0)
        r2 = self._create_report(1, distance_run_nm=210.0)
        r3 = self._create_report(2, distance_run_nm=195.0)
        for r in (r1, r2, r3):
            r.action_submit()
            r.action_approve()
        # Report draft tidak ikut terhitung.
        self._create_report(3, distance_run_nm=999.0)

        self.assertEqual(self.voyage.total_distance_nm, 220.0 + 210.0 + 195.0)

    def test_02_rejected_report_keeps_history(self):
        """Reject noon report -> record lama tetap ada, Nakhoda bisa buat record baru."""
        report = self._create_report(10)
        report.action_submit()
        report.rejection_reason = 'Data tidak lengkap'
        report.action_reject()

        self.assertEqual(report.state, 'rejected')

        resubmit = self._create_report(10, distance_run_nm=180.0,
                                        report_datetime=self.base + timedelta(days=10, hours=1))
        resubmit.action_submit()
        resubmit.action_approve()

        # Record lama masih ada dan tetap rejected (tidak terhapus/tertimpa).
        still_exists = self.env['vessel.noon.report'].search([('id', '=', report.id)])
        self.assertEqual(len(still_exists), 1)
        self.assertEqual(still_exists.state, 'rejected')
        self.assertEqual(resubmit.state, 'approved')

    def test_03_lat_long_range_constraint(self):
        """Latitude/longitude di luar range -90..90 / -180..180 -> ValidationError."""
        with self.assertRaises(ValidationError):
            self._create_report(20, latitude=95.0)
        with self.assertRaises(ValidationError):
            self._create_report(21, longitude=185.0)

    @mute_logger('odoo.sql_db')
    def test_04_unique_voyage_datetime_constraint(self):
        """Dua noon report dengan voyage_id + report_datetime sama -> IntegrityError."""
        self._create_report(30)
        with self.assertRaises(IntegrityError):
            self._create_report(30)
            self.env.flush_all()
