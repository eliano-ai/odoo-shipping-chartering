# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class VesselVoyagePnlLine(models.Model):
    _name = 'vessel.voyage.pnl.line'
    _description = 'Rincian P&L Voyage (Traceability)'
    _order = 'pnl_id, id'

    pnl_id = fields.Many2one(
        'vessel.voyage.pnl', string='Voyage P&L', required=True, ondelete='cascade',
    )
    cost_category_id = fields.Many2one(
        'vessel.pnl.cost.category', string='Kategori Biaya', required=True,
    )
    category_group = fields.Selection(
        related='cost_category_id.category_group', store=True, readonly=True,
    )
    source_model = fields.Char(string='Model Sumber')
    source_res_id = fields.Integer(string='ID Sumber')
    description = fields.Char(string='Deskripsi')
    currency_id = fields.Many2one(related='pnl_id.currency_id', store=True, readonly=True)
    amount = fields.Monetary(
        string='Jumlah',
        help='Positif untuk revenue, negatif untuk cost — konvensi tanda konsisten.',
    )
    is_allocated = fields.Boolean(string='Alokasi Biaya Tidak Langsung')
    allocation_rule_id = fields.Many2one(
        'vessel.cost.allocation.rule', string='Aturan Alokasi',
    )
    is_manual_adjustment = fields.Boolean(string='Adjustment Manual')

    @api.depends('pnl_id.display_name', 'cost_category_id.name', 'description')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('%(pnl)s — %(cat)s') % {
                'pnl': rec.pnl_id.display_name or _('Voyage P&L'),
                'cat': rec.cost_category_id.name or rec.description or _('Baris'),
            }

    def action_view_source(self):
        self.ensure_one()
        if not self.source_model or not self.source_res_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.source_model,
            'res_id': self.source_res_id,
            'view_mode': 'form',
            'target': 'current',
        }
