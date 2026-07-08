# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


PORT_CALL_TYPE = [
    ('load', 'Load'),
    ('discharge', 'Discharge'),
]

STATE = [
    ('draft', 'Draft'),
    ('submitted', 'Submitted'),
    ('approved', 'Approved'),
    ('invoiced', 'Invoiced'),
]


class VesselLaytimeCalculation(models.Model):
    _name = 'vessel.laytime.calculation'
    _description = 'Laytime Calculation (Demurrage/Despatch)'
    _inherit = ['mail.thread']
    _order = 'contract_id, port_call_type'

    contract_id = fields.Many2one(
        'vessel.charter.contract', string='Kontrak',
        required=True, ondelete='cascade', index=True,
    )
    port_call_type = fields.Selection(PORT_CALL_TYPE, string='Tipe Port Call', required=True)
    port_id = fields.Many2one(
        'res.partner', string='Pelabuhan', domain=[('is_port', '=', True)],
    )
    currency_id = fields.Many2one(
        related='contract_id.currency_id', string='Currency', readonly=True,
    )

    # ── NOR & Laytime Window ──────────────────────────────────────────────
    nor_tendered = fields.Datetime(string='NOR Tendered')
    nor_accepted = fields.Datetime(string='NOR Accepted')
    laytime_commenced = fields.Datetime(
        string='Laytime Commenced', compute='_compute_laytime_commenced',
        store=True, readonly=False,
        help='Default = NOR Accepted + Turn Time (dari kontrak). Bisa di-override manual.',
    )
    laytime_completed = fields.Datetime(string='Laytime Completed')
    laytime_allowed_hours = fields.Float(
        string='Laytime Allowed (jam)',
        help='Default dari kontrak sesuai port_call_type (load/discharge). Bisa di-override.',
    )

    sof_line_ids = fields.One2many(
        'vessel.sof.line', 'laytime_id', string='SOF Lines',
    )

    # ── Hasil Compute ─────────────────────────────────────────────────────
    laytime_used_hours = fields.Float(
        string='Laytime Used (jam)', compute='_compute_laytime_used_hours', store=True,
    )
    balance_hours = fields.Float(
        string='Balance (jam)', compute='_compute_balance', store=True,
        help='Allowed - Used. Negatif = on demurrage, positif = despatch.',
    )
    time_on_demurrage_hours = fields.Float(
        string='Time on Demurrage (jam)', compute='_compute_balance', store=True,
    )
    demurrage_amount = fields.Monetary(
        string='Demurrage Amount', compute='_compute_balance', store=True,
        currency_field='currency_id',
    )
    despatch_amount = fields.Monetary(
        string='Despatch Amount', compute='_compute_balance', store=True,
        currency_field='currency_id',
    )

    state = fields.Selection(
        STATE, string='Status', default='draft', required=True,
        tracking=True, copy=False, index=True,
    )
    notes = fields.Html(string='Catatan')
    company_id = fields.Many2one(
        related='contract_id.company_id', store=True, readonly=True,
    )

    # ─────────────────────────────────────────────────────────────────────
    # Onchange / Defaults
    # ─────────────────────────────────────────────────────────────────────

    @api.onchange('contract_id', 'port_call_type')
    def _onchange_contract_port_call_type(self):
        if self.contract_id and self.port_call_type:
            self.port_id = (
                self.contract_id.load_port_id if self.port_call_type == 'load'
                else self.contract_id.discharge_port_id
            )
            self.laytime_allowed_hours = (
                self.contract_id.laytime_allowed_load if self.port_call_type == 'load'
                else self.contract_id.laytime_allowed_discharge
            )

    @api.depends('contract_id.name', 'port_call_type')
    def _compute_display_name(self):
        labels = dict(self._fields['port_call_type'].selection)
        for rec in self:
            rec.display_name = _('%(contract)s — Laytime %(type)s') % {
                'contract': rec.contract_id.name or _('Kontrak'),
                'type': labels.get(rec.port_call_type, rec.port_call_type or ''),
            }

    @api.depends('nor_accepted', 'contract_id.turn_time_hours')
    def _compute_laytime_commenced(self):
        for rec in self:
            if rec.nor_accepted:
                rec.laytime_commenced = rec.nor_accepted + timedelta(
                    hours=rec.contract_id.turn_time_hours or 0.0
                )
            else:
                rec.laytime_commenced = False

    # ─────────────────────────────────────────────────────────────────────
    # Compute — inti algoritma laytime
    # ─────────────────────────────────────────────────────────────────────

    @api.depends('sof_line_ids', 'sof_line_ids.duration_hours', 'sof_line_ids.is_counting',
                 'sof_line_ids.datetime_start', 'laytime_allowed_hours')
    def _compute_laytime_used_hours(self):
        for rec in self:
            lines = rec.sof_line_ids.sorted('datetime_start')
            allowed = rec.laytime_allowed_hours
            used_hours = 0.0
            counting_total = 0.0
            on_demurrage = False
            for line in lines:
                if on_demurrage:
                    # Once on demurrage, always on demurrage — semua waktu
                    # setelah titik ini dihitung, termasuk interupsi non-counting.
                    used_hours += line.duration_hours
                    continue
                if line.is_counting:
                    used_hours += line.duration_hours
                    counting_total += line.duration_hours
                    if allowed and counting_total >= allowed:
                        on_demurrage = True
                # else: interupsi non-counting sebelum on-demurrage — dikecualikan
            rec.laytime_used_hours = used_hours

    @api.depends('laytime_allowed_hours', 'laytime_used_hours', 'contract_id.demurrage_rate',
                 'contract_id.despatch_rate')
    def _compute_balance(self):
        for rec in self:
            balance = rec.laytime_allowed_hours - rec.laytime_used_hours
            rec.balance_hours = balance
            if balance < 0:
                rec.time_on_demurrage_hours = abs(balance)
                rec.demurrage_amount = (abs(balance) / 24.0) * rec.contract_id.demurrage_rate
                rec.despatch_amount = 0.0
            else:
                rec.time_on_demurrage_hours = 0.0
                rec.demurrage_amount = 0.0
                rec.despatch_amount = (balance / 24.0) * rec.contract_id.despatch_rate

    # ─────────────────────────────────────────────────────────────────────
    # State machine
    # ─────────────────────────────────────────────────────────────────────

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Hanya laytime Draft yang bisa di-submit.'))
            rec.state = 'submitted'

    def action_approve(self):
        if not self.env.user.has_group('vessel_chartering.group_chartering_manager'):
            raise UserError(_('Hanya Chartering Manager yang bisa approve laytime.'))
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Hanya laytime Submitted yang bisa di-approve.'))
            rec.state = 'approved'
            rec.message_post(body=_(
                'Laytime approved. Balance: %(balance).2f jam, Demurrage: %(dem)s, Despatch: %(des)s'
            ) % {
                'balance': rec.balance_hours,
                'dem': rec.demurrage_amount,
                'des': rec.despatch_amount,
            })
            if rec.demurrage_amount > 0:
                rec._send_demurrage_approved_email()

    def _send_demurrage_approved_email(self):
        """Notifikasi ke partner — opsional, hanya jika ada email partner terisi."""
        self.ensure_one()
        template = self.env.ref(
            'vessel_chartering.email_template_demurrage_approved', raise_if_not_found=False,
        )
        partner = self.contract_id.partner_id
        if template and partner and partner.email:
            try:
                template.send_mail(self.id, force_send=True, raise_exception=False)
            except Exception as e:
                _logger.warning(
                    'Gagal kirim email demurrage approved untuk %s: %s', self.contract_id.name, e,
                )

    def action_reset_draft(self):
        for rec in self:
            if rec.state == 'invoiced':
                raise UserError(_('Laytime yang sudah Invoiced tidak bisa direset.'))
            rec.state = 'draft'

    def action_create_invoice(self):
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_('Hanya laytime Approved yang bisa dibuat invoice.'))
        if self.demurrage_amount > 0:
            move = self.contract_id._create_demurrage_invoice(self)
        elif self.despatch_amount > 0:
            move = self.contract_id._create_despatch_document(self)
        else:
            raise UserError(_(
                'Tidak ada demurrage/despatch untuk laytime ini (balance = 0).'
            ))
        self.state = 'invoiced'
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoice — %s') % self.contract_id.name,
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
            'target': 'current',
        }
