# -*- coding: utf-8 -*-
from odoo import api, fields, models


class VesselVoyageVoyagePnl(models.Model):
    _inherit = 'vessel.voyage'

    # One2many teknis (tidak ditampilkan di view) semata supaya _compute_pnl_id
    # punya jalur dependency yang benar ke relasi balik — depends('state') SALAH
    # (pernah dicoba, tidak pernah retrigger saat vessel.voyage.pnl baru dibuat
    # dari sisi lain karena state voyage tidak berubah saat itu terjadi).
    pnl_ids = fields.One2many('vessel.voyage.pnl', 'voyage_id')
    pnl_id = fields.Many2one(
        'vessel.voyage.pnl', string='Voyage P&L',
        compute='_compute_pnl_id', store=True,
    )

    @api.depends('pnl_ids')
    def _compute_pnl_id(self):
        for voyage in self:
            voyage.pnl_id = voyage.pnl_ids[:1]

    def action_generate_pnl(self):
        self.ensure_one()
        pnl = self.env['vessel.voyage.pnl'].create({'voyage_id': self.id})
        pnl.action_generate_pnl()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'vessel.voyage.pnl',
            'res_id': pnl.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_pnl(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'vessel.voyage.pnl',
            'res_id': self.pnl_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
