# -*- coding: utf-8 -*-
from odoo import api, fields, models


class VesselVoyageBunkerManagement(models.Model):
    _inherit = 'vessel.voyage'

    bunker_inquiry_ids = fields.One2many(
        'vessel.bunker.inquiry', 'voyage_id', string='Bunker Inquiries',
    )
    bunker_delivery_ids = fields.One2many(
        'vessel.bunker.delivery', compute='_compute_bunker_delivery_ids',
        string='Bunker Deliveries',
    )
    rob_reconciliation_ids = fields.One2many(
        'vessel.bunker.rob.reconciliation', 'voyage_id', string='ROB Reconciliations',
    )
    rob_anomaly_count = fields.Integer(
        string='ROB Anomalies', compute='_compute_rob_anomaly_count',
    )

    @api.depends('bunker_inquiry_ids.delivery_ids')
    def _compute_bunker_delivery_ids(self):
        for voyage in self:
            voyage.bunker_delivery_ids = voyage.bunker_inquiry_ids.delivery_ids

    @api.depends('rob_reconciliation_ids.is_anomaly')
    def _compute_rob_anomaly_count(self):
        for voyage in self:
            voyage.rob_anomaly_count = len(
                voyage.rob_reconciliation_ids.filtered('is_anomaly')
            )

    def action_view_rob_reconciliations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'ROB Reconciliation',
            'res_model': 'vessel.bunker.rob.reconciliation',
            'view_mode': 'list,form',
            'domain': [('voyage_id', '=', self.id)],
        }
