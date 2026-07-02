# -*- coding: utf-8 -*-
from odoo import fields, models


class VesselCharterCancelWizard(models.TransientModel):
    _name = 'vessel.charter.cancel.wizard'
    _description = 'Wizard Batalkan Kontrak Charter'

    contract_id = fields.Many2one(
        'vessel.charter.contract', string='Kontrak',
        required=True, readonly=True,
    )
    reason = fields.Text(string='Alasan Pembatalan', required=True)

    def action_confirm_cancel(self):
        self.ensure_one()
        self.contract_id.write({'state': 'cancelled'})
        self.contract_id.message_post(
            body='Kontrak dibatalkan. Alasan: %s' % self.reason
        )
        return {'type': 'ir.actions.act_window_close'}
