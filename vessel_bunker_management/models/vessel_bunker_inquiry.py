# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

STATE = [
    ('draft', 'Draft'),
    ('inquiry_sent', 'Inquiry Sent'),
    ('quotes_received', 'Quotes Received'),
    ('nominated', 'Nominated'),
    ('delivered', 'Delivered'),
    ('cancelled', 'Cancelled'),
]


class VesselBunkerInquiry(models.Model):
    _name = 'vessel.bunker.inquiry'
    _description = 'Bunker Inquiry (Procurement)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_needed desc, id desc'

    name = fields.Char(
        string='Nomor Inquiry', readonly=True, copy=False,
        default=lambda self: _('New'),
    )
    vessel_id = fields.Many2one('fleet.vehicle', string='Kapal', required=True, tracking=True)
    voyage_id = fields.Many2one(
        'vessel.voyage', string='Voyage',
        help='Opsional — jika bunker untuk kebutuhan voyage spesifik.',
    )
    port_id = fields.Many2one(
        'res.partner', string='Pelabuhan', domain=[('is_port', '=', True)],
    )
    date_needed = fields.Date(string='Tanggal Dibutuhkan', required=True, tracking=True)
    requested_qty_fo = fields.Float(string='Requested Qty FO (MT)')
    requested_qty_do = fields.Float(string='Requested Qty DO (MT)')
    quote_ids = fields.One2many('vessel.bunker.quote', 'inquiry_id', string='Quotes')
    selected_quote_id = fields.Many2one(
        'vessel.bunker.quote', string='Quote Terpilih',
        domain="[('inquiry_id', '=', id)]",
    )
    purchase_order_id = fields.Many2one('purchase.order', string='Purchase Order', readonly=True, copy=False)
    # delivery_ids (One2many vessel.bunker.delivery) ditambahkan Sprint 24 — model
    # delivery belum ada di sprint ini, pola inkremental sama seperti vessel_voyage_pnl.
    state = fields.Selection(STATE, default='draft', required=True, tracking=True, copy=False)
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account', compute='_compute_analytic_account_id', store=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Perusahaan', required=True,
        default=lambda self: self.env.company,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('vessel.bunker.inquiry') or _('New')
        return super().create(vals_list)

    @api.depends('voyage_id.analytic_account_id', 'vessel_id.analytic_account_id')
    def _compute_analytic_account_id(self):
        for rec in self:
            rec.analytic_account_id = (
                rec.voyage_id.analytic_account_id or rec.vessel_id.analytic_account_id
            )

    @api.constrains('selected_quote_id', 'quote_ids')
    def _check_selected_quote_belongs_to_inquiry(self):
        for rec in self:
            if rec.selected_quote_id and rec.selected_quote_id not in rec.quote_ids:
                raise ValidationError(_(
                    'Quote terpilih harus salah satu dari quote milik inquiry ini.'
                ))

    def action_send_inquiry(self):
        """§4.1 — menandai inquiry resmi dikirim ke pasar (supplier balas via quote
        yang diinput staff, bukan email otomatis per-quote karena quote belum ada
        saat transisi ini terjadi — lihat catatan desain Sprint 23)."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Hanya inquiry Draft yang bisa dikirim.'))
            rec.state = 'inquiry_sent'

    def action_nominate(self):
        for rec in self:
            if rec.state not in ('inquiry_sent', 'quotes_received'):
                raise UserError(_('Nominasi hanya bisa dilakukan setelah inquiry terkirim.'))
            if not rec.selected_quote_id:
                raise UserError(_('Pilih quote terlebih dahulu sebelum nominasi.'))
            rec.purchase_order_id = rec._create_purchase_order()
            rec.state = 'nominated'

    def _demo_nominate_if_needed(self, quote_xmlid=False):
        """Wrapper idempoten untuk demo data — <function> tag selalu re-run tiap -u,
        tapi action_nominate() sendiri menolak re-run kalau state sudah bukan
        inquiry_sent/quotes_received. Guard di sini supaya -u berulang tidak error.
        Set selected_quote_id di sini juga (bukan via <record> block terpisah di XML
        — forward-reference 2-block pattern terbukti tidak reliable untuk M2O yang
        target-nya baru dibuat di block SETELAHNYA pada file yang sama)."""
        for rec in self:
            if rec.state in ('inquiry_sent', 'quotes_received'):
                if quote_xmlid and not rec.selected_quote_id:
                    rec.selected_quote_id = self.env.ref(quote_xmlid).id
                if rec.selected_quote_id:
                    rec.action_nominate()

    def _create_purchase_order(self):
        self.ensure_one()
        quote = self.selected_quote_id
        lines = []
        analytic_distribution = (
            {str(self.analytic_account_id.id): 100} if self.analytic_account_id else {}
        )
        if self.requested_qty_fo:
            lines.append((0, 0, {
                'product_id': self.env.ref('vessel_bunker_management.product_bunker_fo').id,
                'name': _('Bunker FO — %s') % self.name,
                'product_qty': self.requested_qty_fo,
                'price_unit': quote.price_fo_usd_mt,
                'analytic_distribution': analytic_distribution,
            }))
        if self.requested_qty_do:
            lines.append((0, 0, {
                'product_id': self.env.ref('vessel_bunker_management.product_bunker_do').id,
                'name': _('Bunker DO — %s') % self.name,
                'product_qty': self.requested_qty_do,
                'price_unit': quote.price_do_usd_mt,
                'analytic_distribution': analytic_distribution,
            }))
        if quote.barging_fee_usd:
            lines.append((0, 0, {
                'product_id': self.env.ref('vessel_bunker_management.product_bunker_barging_fee').id,
                'name': _('Barging Fee — %s') % self.name,
                'product_qty': 1,
                'price_unit': quote.barging_fee_usd,
                'analytic_distribution': analytic_distribution,
            }))
        return self.env['purchase.order'].create({
            'partner_id': quote.supplier_id.id,
            'origin': self.name,
            'order_line': lines,
        })

    def action_cancel(self, reason=False):
        for rec in self:
            if rec.state not in ('draft', 'inquiry_sent', 'quotes_received'):
                raise UserError(_(
                    'Hanya inquiry Draft/Inquiry Sent/Quotes Received yang bisa dibatalkan.'
                ))
            if reason:
                rec.message_post(body=_('Dibatalkan. Alasan: %s') % reason)
            rec.state = 'cancelled'
