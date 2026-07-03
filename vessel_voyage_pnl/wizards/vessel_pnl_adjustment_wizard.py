# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class VesselPnlAdjustmentWizard(models.TransientModel):
    _name = 'vessel.pnl.adjustment.wizard'
    _description = 'Adjustment Manual Voyage P&L (setelah Locked)'

    pnl_id = fields.Many2one('vessel.voyage.pnl', string='Voyage P&L', required=True)
    cost_category_id = fields.Many2one(
        'vessel.pnl.cost.category', string='Kategori Biaya', required=True,
    )
    amount = fields.Monetary(
        string='Jumlah', required=True,
        currency_field='currency_id',
        help='Positif untuk revenue, negatif untuk cost — konvensi tanda sama seperti '
             'baris rincian P&L lainnya.',
    )
    currency_id = fields.Many2one(related='pnl_id.currency_id', readonly=True)
    reason = fields.Text(string='Alasan', required=True)

    def action_apply(self):
        self.ensure_one()
        if self.pnl_id.state != 'locked':
            raise UserError(_('Adjustment manual hanya berlaku untuk P&L yang sudah Locked.'))
        if not self.amount:
            raise UserError(_('Jumlah adjustment tidak boleh nol.'))
        self.env['vessel.voyage.pnl.line'].create({
            'pnl_id': self.pnl_id.id,
            'cost_category_id': self.cost_category_id.id,
            'amount': self.amount,
            'description': _('Adjustment Manual: %s') % self.reason,
            'is_manual_adjustment': True,
        })
        self.pnl_id.message_post(
            body=_(
                'Adjustment manual %(category)s: %(amount)s %(currency)s. Alasan: %(reason)s'
            ) % {
                'category': self.cost_category_id.name,
                'amount': self.amount,
                'currency': self.currency_id.name,
                'reason': self.reason,
            },
        )
        return {'type': 'ir.actions.act_window_close'}
