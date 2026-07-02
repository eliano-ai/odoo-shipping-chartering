# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FleetModelSparepart(models.Model):
    """
    Sparepart yang dialokasikan ke unit kapal (fleet.vehicle).

    Lookup ke product.product yang dikategorikan sebagai "Vessel Inventory".
    Data master (nama, part number, vendor, harga) ditarik otomatis dari produk;
    qty_onhand ditarik real-time dari stock.quant;
    qty_allocated adalah jumlah yang secara khusus dialokasikan ke kapal ini.
    """
    _name = 'fleet.model.sparepart'
    _description = 'Fleet Model Sparepart'
    _order = 'sequence, id'
    _rec_name = 'display_name'

    # ─── Identity ────────────────────────────────────────────────────────────
    sequence = fields.Integer(default=10)

    # ─── Product Lookup (filtered by Vessel Inventory category) ──────────────
    product_id = fields.Many2one(
        'product.product',
        string='Sparepart',
        required=True,
        ondelete='restrict',
        index=True,
        domain="[('categ_id.complete_name', 'ilike', 'Vessel Inventory')]",
        help='Pilih sparepart dari produk berkategori "Vessel Inventory" di Inventory.',
    )

    # ─── Auto-populated from product (readonly, refreshed on product change) ──
    part_number = fields.Char(
        string='Part Number',
        compute='_compute_from_product',
        store=True,
        readonly=False,
        help='Default dari Internal Reference produk. Bisa di-override.',
    )
    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor / Supplier',
        compute='_compute_from_product',
        store=True,
        readonly=False,
        help='Default dari vendor utama produk. Bisa di-override.',
    )
    price_unit = fields.Float(
        string='Unit Cost',
        digits='Product Price',
        compute='_compute_from_product',
        store=True,
        readonly=False,
        help='Default dari standard_price (Cost) produk. Bisa di-override.',
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        compute='_compute_from_product',
        store=True,
        readonly=False,
    )
    product_category_id = fields.Many2one(
        'product.category',
        string='Product Category',
        related='product_id.categ_id',
        store=True,
        readonly=True,
    )
    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name_field',
        store=True,
    )

    # ─── Vehicle / Vessel ────────────────────────────────────────────────────
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle / Vessel',
        required=True,
        ondelete='cascade',
        index=True,
    )
    vehicle_model_id = fields.Many2one(
        related='vehicle_id.model_id',
        string='Vehicle Model',
        store=True,
        readonly=True,
    )

    # ─── Quantity: On-hand (real-time) + Allocated ───────────────────────────
    qty_onhand = fields.Float(
        string='On-Hand Qty',
        compute='_compute_qty_onhand',
        digits='Product Unit of Measure',
        help='Stok tersedia real-time dari Inventory (stock.quant). Read-only.',
    )
    qty_allocated = fields.Float(
        string='Allocated Qty',
        digits='Product Unit of Measure',
        default=0.0,
        help='Jumlah yang secara khusus dialokasikan / dicadangkan untuk kapal ini.',
    )
    qty_difference = fields.Float(
        string='Difference',
        compute='_compute_qty_difference',
        digits='Product Unit of Measure',
        help='On-hand dikurangi allocated. Negatif = stok kurang.',
    )

    # ─── Cost ────────────────────────────────────────────────────────────────
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )
    subtotal = fields.Monetary(
        string='Subtotal (Allocated)',
        compute='_compute_subtotal',
        store=True,
        currency_field='currency_id',
        help='qty_allocated x unit cost.',
    )

    # ─── Extra ───────────────────────────────────────────────────────────────
    note = fields.Text(string='Notes')
    active = fields.Boolean(default=True)

    # ─── Computed: pull from product ─────────────────────────────────────────
    @api.depends('product_id')
    def _compute_from_product(self):
        for rec in self:
            if not rec.product_id:
                rec.part_number = False
                rec.vendor_id = False
                rec.price_unit = 0.0
                rec.uom_id = False
                continue
            rec.part_number = rec.product_id.default_code or False
            rec.uom_id = rec.product_id.uom_id
            rec.price_unit = rec.product_id.standard_price
            supplierinfo = rec.product_id.seller_ids.sorted('sequence')[:1]
            rec.vendor_id = supplierinfo.partner_id if supplierinfo else False

    @api.depends('product_id')
    def _compute_display_name_field(self):
        for rec in self:
            rec.display_name = rec.product_id.display_name if rec.product_id else _('New Sparepart')

    def _compute_qty_onhand(self):
        for rec in self:
            rec.qty_onhand = rec.product_id.qty_available if rec.product_id else 0.0

    @api.depends('qty_onhand', 'qty_allocated')
    def _compute_qty_difference(self):
        for rec in self:
            rec.qty_difference = rec.qty_onhand - rec.qty_allocated

    @api.depends('qty_allocated', 'price_unit')
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = rec.qty_allocated * rec.price_unit

    # ─── Onchange ─────────────────────────────────────────────────────────────
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.price_unit = self.product_id.standard_price
            self.uom_id = self.product_id.uom_id
            self.part_number = self.product_id.default_code or False
            supplierinfo = self.product_id.seller_ids.sorted('sequence')[:1]
            self.vendor_id = supplierinfo.partner_id if supplierinfo else False

    # ─── Constraints ─────────────────────────────────────────────────────────
    @api.constrains('qty_allocated')
    def _check_qty_allocated(self):
        for rec in self:
            if rec.qty_allocated < 0:
                raise ValidationError(_('Allocated quantity cannot be negative.'))

    @api.constrains('product_id', 'vehicle_id')
    def _check_unique_product_per_vehicle(self):
        for rec in self:
            duplicate = self.search([
                ('product_id', '=', rec.product_id.id),
                ('vehicle_id', '=', rec.vehicle_id.id),
                ('id', '!=', rec.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'Product "%s" is already allocated to vessel "%s". '
                    'Update the existing line instead of adding a duplicate.'
                ) % (rec.product_id.display_name, rec.vehicle_id.name))

    def action_open_product(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.product',
            'view_mode': 'form',
            'res_id': self.product_id.id,
            'target': 'current',
        }
