# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class VesselBunkerQuote(models.Model):
    _name = 'vessel.bunker.quote'
    _description = 'Bunker Quote (per Supplier)'
    _order = 'inquiry_id, id'

    inquiry_id = fields.Many2one(
        'vessel.bunker.inquiry', string='Inquiry', required=True, ondelete='cascade',
    )
    supplier_id = fields.Many2one('res.partner', string='Supplier', required=True)
    price_fo_usd_mt = fields.Float(string='Harga FO (USD/MT)')
    price_do_usd_mt = fields.Float(string='Harga DO (USD/MT)')
    barging_fee_usd = fields.Float(string='Barging Fee (USD)')
    validity_date = fields.Date(string='Berlaku Sampai')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.ref('base.USD', raise_if_not_found=False),
    )
    total_estimated_usd = fields.Monetary(
        string='Total Estimasi (USD)', compute='_compute_total_estimated_usd', store=True,
    )
    price_vs_market_pct = fields.Float(
        string='Selisih vs Harga Pasar (%)', compute='_compute_price_vs_market_pct', store=True,
        help='Dibandingkan terhadap vessel.bunker.price.reference tanggal terdekat '
             'sebelum validity_date — weighted rata-rata FO/DO sesuai proporsi qty diminta.',
    )
    notes = fields.Char()

    @api.depends('inquiry_id.name', 'supplier_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('%(inquiry)s — %(supplier)s') % {
                'inquiry': rec.inquiry_id.name or _('Inquiry'),
                'supplier': rec.supplier_id.name or _('Supplier'),
            }

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        inquiries = records.inquiry_id.filtered(lambda i: i.state == 'inquiry_sent')
        if inquiries:
            inquiries.write({'state': 'quotes_received'})
            # §Sprint 27 — notifikasi INTERNAL (bukan email ke supplier, lihat catatan
            # desain action_send_inquiry) saat quote PERTAMA masuk untuk inquiry ini,
            # mengonfirmasi harga sudah bisa dibandingkan/dinominasi.
            template = self.env.ref(
                'vessel_bunker_management.email_template_bunker_quotes_received',
                raise_if_not_found=False,
            )
            if template:
                for inquiry in inquiries:
                    template.send_mail(inquiry.id, force_send=False)
        return records

    @api.depends('price_fo_usd_mt', 'price_do_usd_mt', 'barging_fee_usd',
                 'inquiry_id.requested_qty_fo', 'inquiry_id.requested_qty_do')
    def _compute_total_estimated_usd(self):
        for rec in self:
            inquiry = rec.inquiry_id
            rec.total_estimated_usd = (
                rec.price_fo_usd_mt * inquiry.requested_qty_fo
                + rec.price_do_usd_mt * inquiry.requested_qty_do
                + rec.barging_fee_usd
            )

    @api.depends('price_fo_usd_mt', 'price_do_usd_mt', 'validity_date',
                 'inquiry_id.requested_qty_fo', 'inquiry_id.requested_qty_do')
    def _compute_price_vs_market_pct(self):
        PriceRef = self.env['vessel.bunker.price.reference']
        for rec in self:
            inquiry = rec.inquiry_id
            date_ref = rec.validity_date or fields.Date.context_today(rec)
            quote_total = 0.0
            market_total = 0.0
            for fuel_code, qty, price in (
                ('mfo', inquiry.requested_qty_fo, rec.price_fo_usd_mt),
                ('hsd', inquiry.requested_qty_do, rec.price_do_usd_mt),
            ):
                if not qty:
                    continue
                fuel_type = self.env.ref(
                    'fleet_fuel_log.fuel_type_%s' % fuel_code, raise_if_not_found=False,
                )
                if not fuel_type:
                    continue
                ref = PriceRef.search([
                    ('fuel_type_id', '=', fuel_type.id),
                    ('date', '<=', date_ref),
                ], order='date desc', limit=1)
                if not ref:
                    continue
                quote_total += price * qty
                market_total += ref.price_usd_mt * qty
            rec.price_vs_market_pct = (
                ((quote_total - market_total) / market_total) * 100.0 if market_total else 0.0
            )
