# -*- coding: utf-8 -*-
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
        sesuai quote terpilih."""
        self.assertEqual(self.inquiry.state, 'nominated')
        po = self.inquiry.purchase_order_id
        self.assertTrue(po)
        quote = self.inquiry.selected_quote_id
        fo_line = po.order_line.filtered(
            lambda l: l.product_id == self.env.ref('vessel_bunker_management.product_bunker_fo')
        )
        self.assertEqual(len(fo_line), 1)
        self.assertAlmostEqual(fo_line.price_unit, quote.price_fo_usd_mt, places=2)
        self.assertAlmostEqual(fo_line.product_qty, self.inquiry.requested_qty_fo, places=2)
