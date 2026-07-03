# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

DISBURSEMENT_TYPE = [
    ('pda', 'PDA (Estimasi)'),
    ('fda', 'FDA (Final)'),
]

STATE = [
    ('draft', 'Draft'),
    ('confirmed', 'Confirmed'),
]


class VesselPortDisbursement(models.Model):
    _name = 'vessel.port.disbursement'
    _description = 'Port Disbursement — PDA/FDA'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'port_call_id, disbursement_type'

    port_call_id = fields.Many2one(
        'vessel.port.call', string='Port Call', required=True, ondelete='cascade',
    )
    disbursement_type = fields.Selection(
        DISBURSEMENT_TYPE, string='Tipe', required=True, default='pda',
    )
    agent_id = fields.Many2one(
        'res.partner', string='Agen',
        related='port_call_id.agent_id', store=True, readonly=True,
    )
    company_id = fields.Many2one(
        related='port_call_id.company_id', string='Perusahaan', store=True, readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency', string='Mata Uang',
        default=lambda self: self.env.company.currency_id,
    )
    line_ids = fields.One2many(
        'vessel.port.disbursement.line', 'disbursement_id', string='Line Items',
    )
    total_amount = fields.Monetary(
        string='Total', compute='_compute_total_amount', store=True, currency_field='currency_id',
    )
    variance_amount = fields.Monetary(
        string='Variance', compute='_compute_variance', store=True, currency_field='currency_id',
        help='Hanya terisi di record FDA yang confirmed: total FDA - total PDA (port call sama). '
             '0 kalau PDA belum ada/belum confirmed.',
    )
    variance_pct = fields.Float(
        string='Variance (%)', compute='_compute_variance', store=True,
    )
    state = fields.Selection(
        STATE, string='Status', default='draft', required=True, copy=False,
    )
    reviewed = fields.Boolean(
        string='Sudah Direview', default=False, copy=False,
        help='Ditandai Finance setelah meninjau variance PDA/FDA. Dipakai cron reminder '
             'mingguan (Sprint 13) untuk FDA confirmed dengan variance yang belum direview.',
    )
    document_ids = fields.Many2many('ir.attachment', string='Lampiran')

    @api.depends('line_ids.amount')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped('amount'))

    @api.depends(
        'disbursement_type', 'state', 'total_amount',
        'port_call_id.disbursement_ids.disbursement_type',
        'port_call_id.disbursement_ids.state',
        'port_call_id.disbursement_ids.total_amount',
    )
    def _compute_variance(self):
        for rec in self:
            if rec.disbursement_type != 'fda' or rec.state != 'confirmed':
                rec.variance_amount = 0.0
                rec.variance_pct = 0.0
                continue
            pda = rec.port_call_id.disbursement_ids.filtered(
                lambda d: d.disbursement_type == 'pda' and d.state == 'confirmed'
            )[:1]
            if not pda:
                rec.variance_amount = 0.0
                rec.variance_pct = 0.0
                continue
            rec.variance_amount = rec.total_amount - pda.total_amount
            rec.variance_pct = (
                (rec.variance_amount / pda.total_amount) * 100.0 if pda.total_amount else 0.0
            )

    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Hanya disbursement Draft yang bisa dikonfirmasi.'))
            rec.state = 'confirmed'
            if rec.disbursement_type == 'fda':
                rec._check_variance_threshold()

    def _check_variance_threshold(self):
        """§4.4 — kalau variance_pct > threshold (per-port, fallback default company),
        activity_schedule ke Chartering Manager & Finance."""
        self.ensure_one()
        threshold = self.port_call_id.port_id.disbursement_variance_threshold_pct \
            or self.company_id.default_disbursement_variance_threshold_pct
        if abs(self.variance_pct) <= threshold:
            return
        manager_group = self.env.ref(
            'vessel_voyage_operations.group_voyage_ops_manager', raise_if_not_found=False,
        )
        finance_group = self.env.ref('account.group_account_manager', raise_if_not_found=False)
        recipients = self.env['res.users']
        if manager_group:
            recipients |= manager_group.user_ids
        if finance_group:
            recipients |= finance_group.user_ids
        existing_users = self.env['mail.activity'].search([
            ('res_model', '=', 'vessel.port.disbursement'),
            ('res_id', '=', self.id),
        ]).mapped('user_id')
        for user in recipients - existing_users:
            # Guard idempotency: -u ulang / re-trigger tidak boleh dobel activity
            # untuk record + user yang sama.
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Variance PDA/FDA %(pct).1f%% di atas threshold — %(port)s') % {
                    'pct': self.variance_pct, 'port': self.port_call_id.port_id.display_name,
                },
                note=_(
                    'FDA %(port)s: variance %(amount).2f %(currency)s (%(pct).1f%%), '
                    'threshold %(threshold).1f%%. Perlu review.'
                ) % {
                    'port': self.port_call_id.port_id.display_name,
                    'amount': self.variance_amount, 'currency': self.currency_id.name,
                    'pct': self.variance_pct, 'threshold': threshold,
                },
                user_id=user.id,
            )
