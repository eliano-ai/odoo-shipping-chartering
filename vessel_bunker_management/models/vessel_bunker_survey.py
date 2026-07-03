# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

DISPUTE_STATE = [
    ('open', 'Open'),
    ('resolved', 'Resolved'),
]


class VesselBunkerSurvey(models.Model):
    _name = 'vessel.bunker.survey'
    _description = 'Independent Bunker Survey'
    _order = 'survey_date desc'

    delivery_id = fields.Many2one(
        'vessel.bunker.delivery', string='Delivery', required=True, ondelete='cascade',
    )
    surveyor_id = fields.Many2one('res.partner', string='Surveyor', required=True)
    survey_date = fields.Date()
    survey_qty_mt = fields.Float(string='Survey Qty (MT)', required=True)
    survey_density = fields.Float()
    variance_qty_mt = fields.Float(
        string='Variance Qty (MT)', compute='_compute_variance', store=True,
    )
    variance_pct = fields.Float(
        string='Variance (%)', compute='_compute_variance', store=True,
    )
    tolerance_pct = fields.Float(
        string='Toleransi (%)',
        default=lambda self: self.env.company.default_bdn_survey_tolerance_pct,
    )
    is_dispute = fields.Boolean(
        string='Dispute?', compute='_compute_variance', store=True,
    )
    dispute_state = fields.Selection(DISPUTE_STATE, default='open', copy=False)
    resolution_notes = fields.Html()
    attachment_ids = fields.Many2many('ir.attachment', string='Laporan Survey')

    @api.depends('survey_qty_mt', 'delivery_id.qty_bdn_mt', 'tolerance_pct')
    def _compute_variance(self):
        for rec in self:
            bdn_qty = rec.delivery_id.qty_bdn_mt
            rec.variance_qty_mt = rec.survey_qty_mt - bdn_qty
            rec.variance_pct = (rec.variance_qty_mt / bdn_qty) * 100.0 if bdn_qty else 0.0
            rec.is_dispute = abs(rec.variance_pct) > rec.tolerance_pct

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec.delivery_id.action_link_survey(rec)
        return records

    def action_resolve_dispute(self):
        if not self.env.user.has_group('vessel_bunker_management.group_bunker_manager'):
            raise UserError(_('Hanya Bunker Manager yang bisa resolve dispute.'))
        for rec in self:
            if not rec.resolution_notes:
                raise UserError(_('Catatan resolusi wajib diisi sebelum dispute di-resolve.'))
            rec.dispute_state = 'resolved'
            if rec.delivery_id.state == 'disputed':
                rec.delivery_id.state = 'surveyed'
