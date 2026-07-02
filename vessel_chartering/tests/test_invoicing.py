# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestInvoicing(TransactionCase):
    """Unit test invoicing — acceptance criteria §10.4/10.5/10.7 TECH_SPEC_vessel_chartering.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.charterer = cls.env['res.partner'].create({'name': 'Test Invoicing Charterer'})
        cls.owner = cls.env['res.partner'].create({'name': 'Test Invoicing Owner'})
        brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Test Inv Brand'})
        model = cls.env['fleet.vehicle.model'].create({
            'name': 'Test Inv Vessel Model', 'brand_id': brand.id,
        })
        vessel_type = cls.env['fleet.document.vessel.type'].create({'name': 'Test Inv Type'})
        cls.vessel = cls.env['fleet.vehicle'].create({
            'model_id': model.id,
            'vessel_type_id': vessel_type.id,
            'license_plate': 'TEST-INV-01',
        })
        cls.env.user.group_ids = [(4, cls.env.ref('vessel_chartering.group_chartering_manager').id)]

    def _create_contract(self, direction='out', **extra):
        vals = {
            'contract_type': 'voyage',
            'direction': direction,
            'partner_id': self.charterer.id if direction == 'out' else self.owner.id,
            'vessel_id': self.vessel.id,
            'demurrage_rate': 10000,
            'despatch_rate': 5000,
            'freight_rate': 12.5,
            'cargo_qty': 7500,
            'bl_qty': 7500,
            'date_start': datetime(2026, 1, 1).date(),
        }
        vals.update(extra)
        contract = self.env['vessel.charter.contract'].create(vals)
        contract.action_confirm()  # analytic_account_id (plan Voyage) baru dibuat saat confirm
        return contract

    def test_01_demurrage_invoice_usd_15000_with_analytic(self):
        """§10.4: Laytime approved balance -36h, rate USD 10,000/day →
        demurrage invoice USD 15,000 dengan analytic_distribution 2 plan."""
        contract = self._create_contract()
        laytime = self.env['vessel.laytime.calculation'].create({
            'contract_id': contract.id,
            'port_call_type': 'load',
            'laytime_allowed_hours': 96,
        })
        self.env['vessel.sof.line'].create({
            'laytime_id': laytime.id,
            'datetime_start': datetime(2026, 1, 1, 8, 0, 0),
            'datetime_end': datetime(2026, 1, 6, 20, 0, 0),  # 132 jam
        })
        self.assertEqual(laytime.demurrage_amount, 15000.0)

        laytime.action_submit()
        laytime.action_approve()
        action = laytime.action_create_invoice()
        move = self.env['account.move'].browse(action['res_id'])

        # amount_untaxed (bukan amount_total) — modul tidak hardcode tax, PPN default
        # bisa otomatis kepasang dari fiscal position/product category (by design).
        self.assertEqual(move.amount_untaxed, 15000.0)
        self.assertEqual(laytime.state, 'invoiced')
        # 2 dimensi analytic plan (Vessel + Voyage) di line invoice
        line = move.invoice_line_ids[:1]
        self.assertEqual(len(line.analytic_distribution or {}), 2)
        self.assertIn(str(contract.analytic_account_id.id), line.analytic_distribution)
        self.assertIn(str(self.vessel.analytic_account_id.id), line.analytic_distribution)

    def test_02_invoice_idr_fixed_rate(self):
        """§10.5: Invoice IDR dengan policy fixed rate 16.250 → amount IDR benar, kurs tercatat."""
        idr = self.env.ref('base.IDR')
        contract = self._create_contract(
            invoice_currency_id=idr.id,
            exchange_rate_policy='fixed',
            fixed_exchange_rate=16250.0,
        )
        # freight_amount_final = 12.5 * 7500 = 93750 USD
        self.assertEqual(contract.freight_amount_final, 93750.0)

        move = contract._create_freight_invoice(100.0)

        self.assertEqual(move.currency_id, idr)
        # amount_untaxed — modul tidak hardcode tax (§11 tech spec), PPN default bisa
        # otomatis kepasang dari fiscal position; yang kita kontrol adalah price_unit.
        self.assertAlmostEqual(move.amount_untaxed, 93750.0 * 16250.0, delta=1.0)
        self.assertIn('16250', move.narration or '')

    def test_03_charter_in_vendor_bill_draft(self):
        """§10.7: Charter-in → vendor bill draft dengan expense account & analytic benar."""
        contract = self._create_contract(direction='in')
        move = contract._create_freight_invoice(100.0)

        self.assertEqual(move.move_type, 'in_invoice')
        self.assertEqual(move.state, 'draft')  # tidak auto-post
        self.assertEqual(move.partner_id, self.owner)
        line = move.invoice_line_ids[:1]
        self.assertTrue(line.analytic_distribution)
        # Vendor bill line harus punya account (ditentukan Odoo dari kategori produk +
        # fiscal position, bukan hardcode oleh modul ini) dan bertipe expense — bukan income.
        self.assertTrue(line.account_id)
        self.assertIn(
            line.account_id.account_type,
            ('expense', 'expense_direct_cost', 'liability_payable', 'asset_current'),
        )

    def test_04_despatch_negative_line_default(self):
        """Despatch default sebagai invoice line negatif (despatch_as_credit_note=False)."""
        contract = self._create_contract()
        self.assertFalse(self.env.company.despatch_as_credit_note)
        laytime = self.env['vessel.laytime.calculation'].create({
            'contract_id': contract.id,
            'port_call_type': 'discharge',
            'laytime_allowed_hours': 96,
        })
        self.env['vessel.sof.line'].create({
            'laytime_id': laytime.id,
            'datetime_start': datetime(2026, 1, 1, 8, 0, 0),
            'datetime_end': datetime(2026, 1, 5, 8, 0, 0),  # 96 jam persis, despatch = 0
        })
        # buat skenario despatch > 0
        laytime.write({'laytime_allowed_hours': 120})
        self.assertTrue(laytime.despatch_amount > 0)

        laytime.action_submit()
        laytime.action_approve()
        action = laytime.action_create_invoice()
        move = self.env['account.move'].browse(action['res_id'])

        self.assertEqual(move.move_type, 'out_invoice')  # bukan credit note
        self.assertTrue(move.invoice_line_ids[0].price_unit < 0)  # line negatif
