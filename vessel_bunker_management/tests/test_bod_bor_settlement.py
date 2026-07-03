# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBodBorSettlement(TransactionCase):

    def setUp(self):
        super().setUp()
        self.contract = self.env.ref('vessel_chartering.demo_contract_time_out_1')
        self.bod = self.env['vessel.bunker.bod.bor'].search([
            ('contract_id', '=', self.contract.id), ('event_type', '=', 'delivery'),
        ], limit=1)

    def test_write_hook_creates_draft_bod_bor(self):
        """§10.6 acceptance criteria — delivery_date TERISI (transisi kosong -> ada,
        via write()) -> draft BOD/BOR otomatis. Diuji dengan kontrak time charter
        BARU (bukan demo_contract_time_out_1 yang delivery_date-nya sudah ter-set
        sejak create(), tidak lewat write())."""
        contract = self.env['vessel.charter.contract'].create({
            'contract_type': 'time',
            'direction': 'out',
            'partner_id': self.contract.partner_id.id,
            'vessel_id': self.contract.vessel_id.id,
            'hire_rate': 7500,
        })
        self.assertFalse(contract.bod_bor_ids)
        contract.write({'delivery_date': self.contract.delivery_date})
        self.assertEqual(len(contract.bod_bor_ids), 1)
        self.assertEqual(contract.bod_bor_ids.event_type, 'delivery')
        self.assertEqual(contract.bod_bor_ids.state, 'draft')

    def test_write_hook_idempotent_no_duplicate(self):
        contract = self.env['vessel.charter.contract'].create({
            'contract_type': 'time', 'direction': 'out',
            'partner_id': self.contract.partner_id.id,
            'vessel_id': self.contract.vessel_id.id, 'hire_rate': 7500,
        })
        contract.write({'delivery_date': self.contract.delivery_date})
        contract.write({'delivery_date': self.contract.delivery_date})
        self.assertEqual(len(contract.bod_bor_ids), 1)

    def test_settlement_amount_and_direction(self):
        """§10.7 acceptance criteria — settle -> bunker_adjustment terisi benar
        nilai & tanda (delivery = charterer bayar owner = positif)."""
        self.assertEqual(self.bod.state, 'settled')
        self.assertEqual(self.bod.settlement_direction, 'delivery')
        expected_amount = self.bod.rob_fo * self.bod.price_fo_usd_mt + self.bod.rob_do * self.bod.price_do_usd_mt
        self.assertAlmostEqual(self.bod.settlement_amount, expected_amount, places=2)
        self.assertAlmostEqual(
            self.bod.hire_statement_line_id.bunker_adjustment, expected_amount, places=2,
        )

    def test_redelivery_direction_is_negative(self):
        """settlement_direction redelivery -> owner bayar charterer (amount negatif
        saat ditulis ke hire statement, diuji lewat action_settle langsung)."""
        bod_redelivery = self.env['vessel.bunker.bod.bor'].create({
            'contract_id': self.contract.id,
            'event_type': 'redelivery',
            'rob_fo': 50,
            'rob_do': 10,
            'price_source': 'manual',
            'price_fo_usd_mt': 500,
            'price_do_usd_mt': 700,
        })
        bod_redelivery.state = 'confirmed'
        # period_start beda dari yang dipakai demo _demo_setup_bod_bor_scenario
        # (period_start = contract.delivery_date.date()) — constraint
        # _check_no_duplicate_period unique per (contract_id, period_start).
        period_start = self.contract.delivery_date.date() + timedelta(days=200)
        line = self.env['vessel.hire.statement.line'].create({
            'contract_id': self.contract.id,
            'period_start': period_start,
            'period_end': period_start + timedelta(days=14),
        })
        bod_redelivery.hire_statement_line_id = line.id
        bod_redelivery.with_user(self.env.ref('base.user_admin')).action_settle()
        expected = -(50 * 500 + 10 * 700)
        self.assertAlmostEqual(line.bunker_adjustment, expected, places=2)

    def test_group_bunker_user_cannot_settle(self):
        """§10.8 acceptance criteria (bagian BOD/BOR) — group_bunker_user tidak bisa
        approve BOD/BOR settlement."""
        test_user = self.env['res.users'].create({
            'name': 'Test Bunker User 2',
            'login': 'test_bunker_user_settle',
            'group_ids': [(6, 0, [
                self.env.ref('vessel_bunker_management.group_bunker_user').id,
                self.env.ref('base.group_user').id,
            ])],
        })
        bod = self.env['vessel.bunker.bod.bor'].create({
            'contract_id': self.contract.id,
            'event_type': 'redelivery',
            'rob_fo': 10, 'rob_do': 5,
            'price_source': 'manual',
            'price_fo_usd_mt': 500, 'price_do_usd_mt': 700,
        })
        bod.state = 'confirmed'
        with self.assertRaises(UserError):
            bod.with_user(test_user).action_settle()
