# -*- coding: utf-8 -*-
from odoo import fields, models


class VesselVoyageCancelWizard(models.TransientModel):
    _name = 'vessel.voyage.cancel.wizard'
    _description = 'Wizard Batalkan Voyage'

    voyage_id = fields.Many2one(
        'vessel.voyage', string='Voyage',
        required=True, readonly=True,
    )
    reason = fields.Text(string='Alasan Pembatalan', required=True)

    def action_confirm_cancel(self):
        self.ensure_one()
        self.voyage_id.write({'state': 'cancelled'})
        self.voyage_id.message_post(
            body='Voyage dibatalkan. Alasan: %s' % self.reason
        )
        return {'type': 'ir.actions.act_window_close'}
