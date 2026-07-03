# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPortDisbursement(TransactionCase):
    """Unit test vessel.port.disbursement — acceptance criteria §10.7 tech spec."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        partner = cls.env['res.partner'].create({'name': 'Test Charterer PD'})
        brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Test Brand PD'})
        model = cls.env['fleet.vehicle.model'].create({
            'name': 'Test Vessel Model PD', 'brand_id': brand.id,
        })
        vessel_type = cls.env['fleet.document.vessel.type'].create({'name': 'Test Type PD'})
        vessel = cls.env['fleet.vehicle'].create({
            'model_id': model.id,
            'vessel_type_id': vessel_type.id,
            'license_plate': 'TEST-PDA-01',
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
        voyage = cls.env['vessel.voyage'].create({'charter_contract_id': contract.id})
        port = cls.env['res.partner'].create({'name': 'Test Port PD', 'is_port': True})
        agent = cls.env['res.partner'].create({
            'name': 'Test Agent PD', 'is_port_agent': True,
        })
        cls.port_call = cls.env['vessel.port.call'].create({
            'voyage_id': voyage.id,
            'port_id': port.id,
            'agent_id': agent.id,
            'call_purpose': 'load',
        })
        cls.item_type = cls.env['vessel.disbursement.item.type'].search([], limit=1) or \
            cls.env['vessel.disbursement.item.type'].create({'name': 'Test Item PD'})

    def _create_disbursement(self, disbursement_type, line_amounts):
        disb = self.env['vessel.port.disbursement'].create({
            'port_call_id': self.port_call.id,
            'disbursement_type': disbursement_type,
        })
        for amount in line_amounts:
            self.env['vessel.port.disbursement.line'].create({
                'disbursement_id': disb.id,
                'item_type_id': self.item_type.id,
                'amount': amount,
            })
        return disb

    def test_01_variance_20_pct_above_default_threshold(self):
        """PDA 5 line (total 1,000,000) -> FDA +20% (total 1,200,000) -> variance
        20% > threshold default 15% -> activity terkirim."""
        pda = self._create_disbursement('pda', [200000, 200000, 200000, 200000, 200000])
        pda.action_confirm()
        self.assertEqual(pda.total_amount, 1000000.0)

        fda = self._create_disbursement('fda', [240000, 240000, 240000, 240000, 240000])
        self.assertEqual(fda.total_amount, 1200000.0)
        fda.action_confirm()

        self.assertEqual(fda.variance_amount, 200000.0)
        self.assertAlmostEqual(fda.variance_pct, 20.0, places=2)

        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'vessel.port.disbursement'),
            ('res_id', '=', fda.id),
        ])
        self.assertTrue(activities, 'Activity harus terkirim karena variance 20% > threshold 15%')

    def test_02_variance_below_threshold_no_activity(self):
        """Variance di bawah threshold -> tidak ada activity yang dibuat."""
        pda = self._create_disbursement('pda', [100000])
        pda.action_confirm()

        fda = self._create_disbursement('fda', [105000])  # +5%, di bawah threshold 15%
        fda.action_confirm()

        self.assertAlmostEqual(fda.variance_pct, 5.0, places=2)
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'vessel.port.disbursement'),
            ('res_id', '=', fda.id),
        ])
        self.assertFalse(activities)

    def test_03_variance_zero_without_pda(self):
        """FDA confirmed tanpa PDA confirmed -> variance 0, bukan error."""
        fda = self._create_disbursement('fda', [50000])
        fda.action_confirm()

        self.assertEqual(fda.variance_amount, 0.0)
        self.assertEqual(fda.variance_pct, 0.0)

    def test_04_port_threshold_override(self):
        """Threshold override per-port (lebih rendah dari default) -> variance yang
        tadinya di bawah default threshold, jadi di atas threshold khusus port ini."""
        self.port_call.port_id.disbursement_variance_threshold_pct = 3.0

        pda = self._create_disbursement('pda', [100000])
        pda.action_confirm()
        fda = self._create_disbursement('fda', [105000])  # +5%, di atas threshold port (3%)
        fda.action_confirm()

        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'vessel.port.disbursement'),
            ('res_id', '=', fda.id),
        ])
        self.assertTrue(activities, 'Threshold override 3% harus lebih ketat dari default 15%')
