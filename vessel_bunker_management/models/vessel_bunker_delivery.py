# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

STATE = [
    ('draft', 'Draft'),
    ('delivered', 'Delivered'),
    ('surveyed', 'Surveyed'),
    ('disputed', 'Disputed'),
    ('confirmed', 'Confirmed'),
]


class VesselBunkerDelivery(models.Model):
    _name = 'vessel.bunker.delivery'
    _description = 'Bunker Delivery Note (BDN)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'delivery_datetime desc'

    inquiry_id = fields.Many2one(
        'vessel.bunker.inquiry', string='Inquiry', required=True,
    )
    vessel_id = fields.Many2one(
        'fleet.vehicle', string='Kapal', related='inquiry_id.vessel_id', store=True, readonly=True,
    )
    port_id = fields.Many2one(
        'res.partner', string='Pelabuhan', related='inquiry_id.port_id', store=True, readonly=True,
    )
    bdn_number = fields.Char(string='Nomor BDN', required=True)
    bdn_date = fields.Date()
    delivery_datetime = fields.Datetime(string='Waktu Serah Terima', required=True, tracking=True)
    fuel_type_id = fields.Many2one('fleet.fuel.type', string='Jenis Bahan Bakar', required=True)
    qty_bdn_mt = fields.Float(string='Qty BDN (MT)', required=True)
    density = fields.Float(help='kg/m³ pada 15°C')
    temperature_c = fields.Float(string='Temperature (°C)')
    sulfur_content_pct = fields.Float(string='Sulfur Content (%)')
    attachment_ids = fields.Many2many('ir.attachment', string='Scan BDN')
    survey_id = fields.Many2one('vessel.bunker.survey', string='Independent Survey', copy=False)
    qty_confirmed_mt = fields.Float(
        string='Qty Terkonfirmasi (MT)', compute='_compute_qty_confirmed_mt', store=True,
        help='survey_id.survey_qty_mt kalau ada survey, else qty_bdn_mt — qty yang '
             'dipakai untuk stok & rekonsiliasi ROB.',
    )
    stock_picking_id = fields.Many2one('stock.picking', readonly=True, copy=False)
    account_move_id = fields.Many2one(
        'account.move', string='Vendor Bill', compute='_compute_account_move_id',
    )
    state = fields.Selection(STATE, default='draft', required=True, tracking=True, copy=False)
    company_id = fields.Many2one(
        'res.company', string='Perusahaan', required=True,
        default=lambda self: self.env.company,
    )

    _check_qty_bdn_positive = models.Constraint(
        'CHECK(qty_bdn_mt > 0)', 'Qty BDN harus lebih besar dari 0.',
    )

    @api.depends('survey_id.survey_qty_mt', 'qty_bdn_mt')
    def _compute_qty_confirmed_mt(self):
        for rec in self:
            rec.qty_confirmed_mt = rec.survey_id.survey_qty_mt if rec.survey_id else rec.qty_bdn_mt

    @api.depends('inquiry_id.purchase_order_id.invoice_ids')
    def _compute_account_move_id(self):
        for rec in self:
            rec.account_move_id = rec.inquiry_id.purchase_order_id.invoice_ids[:1]

    def action_mark_delivered(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Hanya BDN Draft yang bisa ditandai Delivered.'))
            rec.state = 'delivered'

    def action_link_survey(self, survey):
        """Dipanggil setelah survey dibuat — update state sesuai hasil is_dispute (§4.2)."""
        self.ensure_one()
        self.survey_id = survey.id
        self.state = 'disputed' if survey.is_dispute else 'surveyed'

    def action_confirm_delivery(self):
        """§4.2 — guard dispute belum resolved, auto-create stock.picking qty_confirmed_mt
        ke lokasi kapal (get-or-create lazy, §Sprint 22 keputusan teknis)."""
        for rec in self:
            if rec.state == 'disputed' and (not rec.survey_id or rec.survey_id.dispute_state != 'resolved'):
                raise UserError(_(
                    'Delivery ini masih dispute — resolve dispute-nya dulu sebelum konfirmasi.'
                ))
            if rec.state not in ('delivered', 'surveyed', 'disputed'):
                raise UserError(_('Delivery harus berstatus Delivered/Surveyed sebelum dikonfirmasi.'))
            rec.stock_picking_id = rec._create_stock_picking()
            rec.state = 'confirmed'
            if rec.inquiry_id.state == 'nominated':
                rec.inquiry_id.state = 'delivered'

    def _create_stock_picking(self):
        self.ensure_one()
        if self.stock_picking_id:
            return self.stock_picking_id
        product = self.fuel_type_id.product_id
        if not product:
            return False
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'), ('company_id', '=', self.company_id.id),
        ], limit=1)
        src_location = self.env.ref('stock.stock_location_suppliers', raise_if_not_found=False)
        dest_location = self.vessel_id._get_bunker_stock_location()
        if not (picking_type and src_location and dest_location):
            return False
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': src_location.id,
            'location_dest_id': dest_location.id,
            'origin': self.bdn_number,
            'move_ids': [(0, 0, {
                'description_picking': _('Bunker Receipt — %s') % self.bdn_number,
                'product_id': product.id,
                'product_uom_qty': self.qty_confirmed_mt,
                'product_uom': (self.fuel_type_id.uom_id or product.uom_id).id,
                'location_id': src_location.id,
                'location_dest_id': dest_location.id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.button_validate()
        return picking

    @api.model
    def _demo_link_fuel_type_products(self):
        """fleet_fuel_log.fuel_type_* tidak punya product_id terisi di seed data modul
        asalnya — tanpa ini, stock.picking bunker delivery tidak pernah ter-generate
        (guard "if not product: return" identik pola fleet_fuel_log sendiri). Reuse
        produk generik FO/DO (bukan bikin produk baru). Pakai write() langsung (bukan
        <record> re-declare di XML) karena fuel_type_* punya ir_model_data noupdate
        milik fleet_fuel_log sendiri — <record> re-declare dari modul lain di-skip,
        write() eksplisit via method ini tidak."""
        fo_product = self.env.ref('vessel_bunker_management.product_bunker_fo', raise_if_not_found=False)
        do_product = self.env.ref('vessel_bunker_management.product_bunker_do', raise_if_not_found=False)
        if not (fo_product and do_product):
            return
        mapping = {'fuel_type_mfo': fo_product, 'fuel_type_hsd': do_product, 'fuel_type_mgo': do_product}
        for xmlid, product in mapping.items():
            fuel_type = self.env.ref('fleet_fuel_log.%s' % xmlid, raise_if_not_found=False)
            if fuel_type and not fuel_type.product_id:
                fuel_type.product_id = product.id

    @api.model
    def _demo_setup_dispute_scenario(self):
        """§10.3/§10.4 acceptance criteria — BDN 500 MT, survey 495 MT, tolerance 0.5%
        -> dispute otomatis, resolve, confirm -> stock.picking qty 495 MT (bukan 500).
        Idempoten — guard cek existing sebelum create tiap langkah."""
        inquiry = self.env.ref('vessel_bunker_management.demo_bunker_inquiry_1', raise_if_not_found=False)
        if not inquiry or inquiry.state not in ('nominated', 'delivered'):
            return
        delivery = self.search([('inquiry_id', '=', inquiry.id)], limit=1)
        if not delivery:
            delivery = self.create({
                'inquiry_id': inquiry.id,
                'bdn_number': 'BDN/2026/0001',
                'bdn_date': fields.Date.context_today(self),
                'delivery_datetime': fields.Datetime.now(),
                'fuel_type_id': self.env.ref('fleet_fuel_log.fuel_type_mfo').id,
                'qty_bdn_mt': 500,
                'density': 991.0,
                'temperature_c': 28.0,
                'sulfur_content_pct': 0.42,
                'state': 'delivered',
            })
        if not delivery.survey_id:
            surveyor = self.env['res.partner'].search([('name', '=', 'PT Independent Surveyor')], limit=1)
            if not surveyor:
                surveyor = self.env['res.partner'].create({
                    'name': 'PT Independent Surveyor', 'is_company': True,
                })
            self.env['vessel.bunker.survey'].create({
                'delivery_id': delivery.id,
                'surveyor_id': surveyor.id,
                'survey_date': fields.Date.context_today(self),
                'survey_qty_mt': 495,
            })
        if delivery.survey_id.is_dispute and delivery.survey_id.dispute_state == 'open':
            # Set field langsung (bukan action_resolve_dispute()) — method itu guard
            # has_group('group_bunker_manager'), tapi user yang jalanin instalasi module
            # (superuser/__system__) belum tentu member grup itu (cuma base.user_admin
            # yang eksplisit di-assign, pelajaran sama seperti vessel_voyage_pnl Sprint 17).
            delivery.survey_id.write({
                'resolution_notes': (
                    'Selisih 5 MT (1%) dikonfirmasi loss transfer wajar, diterima dengan catatan.'
                ),
                'dispute_state': 'resolved',
            })
            delivery.state = 'surveyed'
        if delivery.state in ('delivered', 'surveyed', 'disputed'):
            delivery.action_confirm_delivery()
        elif delivery.state == 'confirmed' and not delivery.stock_picking_id:
            # -u sebelumnya sempat confirm tanpa picking (fleet.fuel.type.product_id
            # belum ke-link saat itu) — coba lagi sekarang produk sudah ada.
            delivery.stock_picking_id = delivery._create_stock_picking()
