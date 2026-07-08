# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBunkerProcurement(TransactionCase):

    def setUp(self):
        super().setUp()
        self.inquiry = self.env.ref('vessel_bunker_management.demo_bunker_inquiry_1')

    def test_total_estimated_usd(self):
        quote = self.env.ref('vessel_bunker_management.demo_bunker_quote_1b')
        expected = (
            quote.price_fo_usd_mt * self.inquiry.requested_qty_fo
            + quote.price_do_usd_mt * self.inquiry.requested_qty_do
            + quote.barging_fee_usd
        )
        self.assertAlmostEqual(quote.total_estimated_usd, expected, places=2)

    def test_price_vs_market_pct_significant_markup(self):
        """§10.9 acceptance criteria — quote jauh di atas referensi -> signifikan."""
        quote_markup = self.env.ref('vessel_bunker_management.demo_bunker_quote_1c')
        self.assertGreater(quote_markup.price_vs_market_pct, 10.0)

    def test_price_vs_market_pct_reasonable_quote(self):
        quote_ok = self.env.ref('vessel_bunker_management.demo_bunker_quote_1b')
        self.assertLess(abs(quote_ok.price_vs_market_pct), 5.0)

    def test_nomination_creates_purchase_order(self):
        """§10.2 acceptance criteria — nominasi -> PO ter-generate dengan line & harga
        sesuai quote terpilih. State inquiry sudah lanjut ke 'delivered' di demo data
        Sprint 24 (BDN confirmed) — cukup pastikan sudah melewati 'nominated', bukan
        stuck di draft/inquiry_sent/quotes_received."""
        self.assertIn(self.inquiry.state, ('nominated', 'delivered'))
        po = self.inquiry.purchase_order_id
        self.assertTrue(po)
        quote = self.inquiry.selected_quote_id
        fo_line = po.order_line.filtered(
            lambda l: l.product_id == self.env.ref('vessel_bunker_management.product_bunker_fo')
        )
        self.assertEqual(len(fo_line), 1)
        self.assertAlmostEqual(fo_line.price_unit, quote.price_fo_usd_mt, places=2)
        self.assertAlmostEqual(fo_line.product_qty, self.inquiry.requested_qty_fo, places=2)

    def test_price_reference_uses_most_recent_before_date(self):
        """vessel.bunker.price.reference — quote._compute_price_vs_market_pct() harus
        pakai baris referensi TERDEKAT sebelum validity_date (order='date desc',
        limit=1), bukan baris pertama/tertua yang match fuel_type. Demo data cuma
        punya 1 baris per fuel_type, jadi logika 'terdekat' ini belum pernah teruji
        dengan >1 baris kompetisi (QA audit 2026-07-03)."""
        mfo_type = self.env.ref('fleet_fuel_log.fuel_type_mfo')
        today = fields.Date.context_today(self.env['vessel.bunker.price.reference'])
        self.env['vessel.bunker.price.reference'].create({
            'date': today - timedelta(days=60), 'index_name': 'mops',
            'fuel_type_id': mfo_type.id, 'price_usd_mt': 500.0,
        })
        self.env['vessel.bunker.price.reference'].create({
            'date': today - timedelta(days=10), 'index_name': 'mops',
            'fuel_type_id': mfo_type.id, 'price_usd_mt': 600.0,
        })
        inquiry = self.env['vessel.bunker.inquiry'].create({
            'vessel_id': self.inquiry.vessel_id.id,
            'date_needed': today,
            'requested_qty_fo': 100,
            'requested_qty_do': 0,
        })
        quote = self.env['vessel.bunker.quote'].create({
            'inquiry_id': inquiry.id,
            'supplier_id': self.env.ref('vessel_bunker_management.demo_supplier_bunker_a').id,
            'price_fo_usd_mt': 600.0,  # sama persis harga referensi TERDEKAT -> variance 0%
            'validity_date': today,
        })
        # Kalau logika salah pakai baris 500 (lebih lama/pertama ditemukan), hasilnya
        # akan +20%, bukan 0%.
        self.assertAlmostEqual(quote.price_vs_market_pct, 0.0, places=2)
