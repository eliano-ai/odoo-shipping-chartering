# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBdnSurveyDispute(TransactionCase):

    def setUp(self):
        super().setUp()
        self.delivery = self.env['vessel.bunker.delivery'].search([
            ('inquiry_id', '=', self.env.ref('vessel_bunker_management.demo_bunker_inquiry_1').id),
        ], limit=1)

    def test_dispute_detected_above_tolerance(self):
        """§10.3 acceptance criteria persis: BDN 500, survey 495, tolerance 0.5% -> dispute."""
        self.assertTrue(self.delivery.survey_id.is_dispute)
        self.assertAlmostEqual(self.delivery.survey_id.variance_pct, -1.0, places=2)

    def test_variance_within_tolerance_not_dispute(self):
        delivery = self.delivery.copy({'bdn_number': 'BDN/2026/TEST-OK'})
        survey = self.env['vessel.bunker.survey'].create({
            'delivery_id': delivery.id,
            'surveyor_id': self.delivery.survey_id.surveyor_id.id,
            'survey_qty_mt': delivery.qty_bdn_mt * 1.001,
        })
        self.assertFalse(survey.is_dispute)

    def test_confirm_blocked_while_disputed(self):
        delivery = self.delivery.copy({'bdn_number': 'BDN/2026/TEST-DISPUTE'})
        self.env['vessel.bunker.survey'].create({
            'delivery_id': delivery.id,
            'surveyor_id': self.delivery.survey_id.surveyor_id.id,
            'survey_qty_mt': delivery.qty_bdn_mt * 0.90,
        })
        self.assertEqual(delivery.state, 'disputed')
        with self.assertRaises(UserError):
            delivery.action_confirm_delivery()

    def test_stock_picking_uses_confirmed_qty_not_bdn_qty(self):
        """§10.4 acceptance criteria persis: stock.picking qty = qty_confirmed_mt (495),
        bukan qty_bdn_mt (500)."""
        self.assertEqual(self.delivery.state, 'confirmed')
        self.assertTrue(self.delivery.stock_picking_id)
        move = self.delivery.stock_picking_id.move_ids[:1]
        self.assertAlmostEqual(move.product_uom_qty, 495.0, places=2)
        self.assertNotAlmostEqual(move.product_uom_qty, 500.0, places=2)

    def test_group_bunker_user_cannot_resolve_dispute(self):
        """§10.8 acceptance criteria (bagian dispute) — group_bunker_user tidak bisa
        resolve dispute."""
        test_user = self.env['res.users'].create({
            'name': 'Test Bunker User',
            'login': 'test_bunker_user_dispute',
            'group_ids': [(6, 0, [
                self.env.ref('vessel_bunker_management.group_bunker_user').id,
                self.env.ref('base.group_user').id,
            ])],
        })
        delivery = self.delivery.copy({'bdn_number': 'BDN/2026/TEST-DISPUTE-2'})
        survey = self.env['vessel.bunker.survey'].create({
            'delivery_id': delivery.id,
            'surveyor_id': self.delivery.survey_id.surveyor_id.id,
            'survey_qty_mt': delivery.qty_bdn_mt * 0.90,
            'resolution_notes': 'Test',
        })
        with self.assertRaises(UserError):
            survey.with_user(test_user).action_resolve_dispute()
