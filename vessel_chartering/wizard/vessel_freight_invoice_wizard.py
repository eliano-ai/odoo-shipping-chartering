# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class VesselFreightInvoiceWizard(models.TransientModel):
    _name = 'vessel.freight.invoice.wizard'
    _description = 'Wizard Buat Invoice Freight'

    contract_id = fields.Many2one(
        'vessel.charter.contract', string='Kontrak',
        required=True, readonly=True,
    )
    bl_qty = fields.Float(related='contract_id.bl_qty', readonly=True)
    freight_rate = fields.Monetary(related='contract_id.freight_rate', readonly=True)
    freight_amount_final = fields.Monetary(related='contract_id.freight_amount_final', readonly=True)
    currency_id = fields.Many2one(related='contract_id.currency_id', readonly=True)
    invoice_currency_id = fields.Many2one(related='contract_id.invoice_currency_id', readonly=True)
    exchange_rate_policy = fields.Selection(related='contract_id.exchange_rate_policy', readonly=True)
    fixed_exchange_rate = fields.Float(related='contract_id.fixed_exchange_rate', readonly=True)

    invoice_pct = fields.Float(
        string='Persentase Diinvoice (%)', required=True, default=100.0,
        help='Persentase dari freight_amount_final yang mau diinvoice sekarang.',
    )
    amount_preview = fields.Monetary(
        string='Preview Amount', compute='_compute_amount_preview',
        currency_field='currency_id',
    )

    @api.depends('contract_id.freight_amount_final', 'invoice_pct')
    def _compute_amount_preview(self):
        for rec in self:
            rec.amount_preview = rec.contract_id.freight_amount_final * (rec.invoice_pct / 100.0)

    def action_confirm(self):
        self.ensure_one()
        move = self.contract_id._create_freight_invoice(self.invoice_pct)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoice — %s') % self.contract_id.name,
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
            'target': 'current',
        }
