# -*- coding: utf-8 -*-
from odoo import fields, models


class VesselCharterContractBunkerManagement(models.Model):
    _inherit = 'vessel.charter.contract'

    bod_bor_ids = fields.One2many(
        'vessel.bunker.bod.bor', 'contract_id', string='BOD/BOR',
    )

    def write(self, vals):
        """Hook §4.4/§12.2 poin 8 — saat delivery_date/redelivery_date TERISI (dari
        kosong ke ada nilai), auto-create draft BOD/BOR. Arah panggilan satu arah:
        method ini ada di modul vessel_bunker_management (extend), BUKAN di
        vessel_chartering — vessel_chartering tidak pernah tahu modul ini ada."""
        was_delivery_empty = {
            rec.id: not rec.delivery_date for rec in self if rec.contract_type == 'time'
        }
        was_redelivery_empty = {
            rec.id: not rec.redelivery_date for rec in self if rec.contract_type == 'time'
        }
        res = super().write(vals)
        for rec in self:
            if rec.contract_type != 'time':
                continue
            if was_delivery_empty.get(rec.id) and rec.delivery_date:
                rec._ensure_bod_bor('delivery')
            if was_redelivery_empty.get(rec.id) and rec.redelivery_date:
                rec._ensure_bod_bor('redelivery')
        return res

    def _ensure_bod_bor(self, event_type):
        self.ensure_one()
        BodBor = self.env['vessel.bunker.bod.bor']
        existing = BodBor.search([
            ('contract_id', '=', self.id), ('event_type', '=', event_type),
        ], limit=1)
        if not existing:
            BodBor.create({'contract_id': self.id, 'event_type': event_type})
