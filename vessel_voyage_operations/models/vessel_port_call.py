# -*- coding: utf-8 -*-
import logging
from datetime import date, timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

CALL_PURPOSE = [
    ('load', 'Load'),
    ('discharge', 'Discharge'),
    ('bunkering', 'Bunkering'),
    ('transit', 'Transit'),
    ('layup', 'Lay-up'),
    ('other', 'Other'),
]


class VesselPortCall(models.Model):
    _name = 'vessel.port.call'
    _description = 'Port Call — Singgah Kapal per Voyage'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'voyage_id, sequence, id'

    voyage_id = fields.Many2one(
        'vessel.voyage', string='Voyage', required=True, ondelete='cascade',
    )
    sequence = fields.Integer(string='Urutan', default=10)
    port_id = fields.Many2one(
        'res.partner', string='Port', required=True, domain=[('is_port', '=', True)],
    )
    call_purpose = fields.Selection(CALL_PURPOSE, string='Tujuan Singgah')
    agent_id = fields.Many2one(
        'res.partner', string='Agen', domain=[('is_port_agent', '=', True)],
    )
    eta = fields.Datetime(string='ETA')
    etb = fields.Datetime(string='ETB')
    etd = fields.Datetime(string='ETD')
    ata = fields.Datetime(string='ATA')
    atb = fields.Datetime(string='ATB')
    atd = fields.Datetime(string='ATD')
    berth_name = fields.Char(string='Dermaga/Anchorage')
    cargo_ops_commenced = fields.Datetime(string='Cargo Ops Mulai')
    cargo_ops_completed = fields.Datetime(string='Cargo Ops Selesai')
    cargo_ops_rate_mt_day = fields.Float(
        string='Rate Cargo Ops (MT/hari)', compute='_compute_cargo_ops_rate_mt_day',
    )
    clearance_line_ids = fields.One2many(
        'vessel.port.clearance.line', 'port_call_id', string='Clearance Checklist',
    )
    disbursement_ids = fields.One2many(
        'vessel.port.disbursement', 'port_call_id', string='PDA/FDA',
    )
    notes = fields.Html(string='Catatan')
    company_id = fields.Many2one(
        related='voyage_id.company_id', string='Perusahaan', store=True, readonly=True,
    )

    @api.depends('voyage_id.name', 'port_id.name', 'sequence')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('%(voyage)s — %(port)s (#%(seq)s)') % {
                'voyage': rec.voyage_id.name or _('Voyage'),
                'port': rec.port_id.name or _('Port'),
                'seq': rec.sequence or '',
            }

    @api.depends(
        'cargo_ops_commenced', 'cargo_ops_completed',
        'voyage_id.cargo_document_ids.qty_mt', 'voyage_id.cargo_document_ids.port_call_id',
    )
    def _compute_cargo_ops_rate_mt_day(self):
        for rec in self:
            if not rec.cargo_ops_commenced or not rec.cargo_ops_completed:
                rec.cargo_ops_rate_mt_day = 0.0
                continue
            duration_days = (rec.cargo_ops_completed - rec.cargo_ops_commenced).total_seconds() / 86400.0
            if duration_days <= 0:
                rec.cargo_ops_rate_mt_day = 0.0
                continue
            docs = rec.voyage_id.cargo_document_ids.filtered(lambda d: d.port_call_id == rec)
            qty = sum(docs.mapped('qty_mt'))
            rec.cargo_ops_rate_mt_day = (qty / duration_days) if qty else 0.0

    @api.constrains('eta', 'etb', 'etd', 'ata', 'atb', 'atd')
    def _check_estimated_actual_sequence(self):
        """Warning (bukan blokir) kalau ETB < ETA / ETD < ETB, atau ATB < ATA / ATD < ATB —
        data lapangan kadang tidak ideal, sesuai keputusan tech spec §3.3."""
        for rec in self:
            warnings = []
            if rec.eta and rec.etb and rec.etb < rec.eta:
                warnings.append(_('ETB lebih awal dari ETA.'))
            if rec.etb and rec.etd and rec.etd < rec.etb:
                warnings.append(_('ETD lebih awal dari ETB.'))
            if rec.ata and rec.atb and rec.atb < rec.ata:
                warnings.append(_('ATB lebih awal dari ATA.'))
            if rec.atb and rec.atd and rec.atd < rec.atb:
                warnings.append(_('ATD lebih awal dari ATB.'))
            if warnings:
                rec.message_post(body=_('⚠️ Peringatan urutan waktu port call %(port)s: %(msg)s') % {
                    'port': rec.port_id.display_name, 'msg': ' '.join(warnings),
                })

    @api.model_create_multi
    def create(self, vals_list):
        calls = super().create(vals_list)
        calls.filtered('call_purpose')._generate_clearance_lines()
        return calls

    def _generate_clearance_lines(self):
        """§4.3 — auto-generate clearance_line_ids dari vessel.clearance.document.type
        yang default_required=True, masing-masing untuk direction in & out."""
        doc_types = self.env['vessel.clearance.document.type'].search([
            ('default_required', '=', True),
        ])
        if not doc_types:
            return
        lines_vals = []
        for call in self:
            if call.clearance_line_ids:
                continue  # jangan generate ulang kalau sudah ada baris (mis. saat -u ulang)
            for doc_type in doc_types:
                for direction in ('in', 'out'):
                    lines_vals.append({
                        'port_call_id': call.id,
                        'document_type_id': doc_type.id,
                        'direction': direction,
                    })
        if lines_vals:
            self.env['vessel.port.clearance.line'].create(lines_vals)

    def _action_create_disbursement(self, disbursement_type):
        self.ensure_one()
        disbursement = self.env['vessel.port.disbursement'].create({
            'port_call_id': self.id,
            'disbursement_type': disbursement_type,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('PDA Baru — %s') % self.port_id.display_name
            if disbursement_type == 'pda' else _('FDA Baru — %s') % self.port_id.display_name,
            'res_model': 'vessel.port.disbursement',
            'view_mode': 'form',
            'res_id': disbursement.id,
            'target': 'current',
        }

    def action_create_pda(self):
        return self._action_create_disbursement('pda')

    def action_create_fda(self):
        return self._action_create_disbursement('fda')

    # ─────────────────────────────────────────────────────────────────────
    # Cron Jobs — Sprint 13
    # ─────────────────────────────────────────────────────────────────────

    @api.model
    def _cron_eta_reminder(self):
        """Harian — port call eta H-2/H-0 tanpa ata terisi → activity Operations
        + email reminder ke agen (kalau agent_id.email ada)."""
        template = self.env.ref(
            'vessel_voyage_operations.email_template_eta_reminder_agent',
            raise_if_not_found=False,
        )
        for days in (2, 0):
            target_date = date.today() + timedelta(days=days)
            calls = self.search([
                ('ata', '=', False),
                ('eta', '>=', target_date.strftime('%Y-%m-%d 00:00:00')),
                ('eta', '<=', target_date.strftime('%Y-%m-%d 23:59:59')),
            ])
            for call in calls:
                existing = self.env['mail.activity'].search([
                    ('res_model', '=', 'vessel.port.call'),
                    ('res_id', '=', call.id),
                    ('summary', 'like', 'ETA H-%s' % days),
                ])
                if existing:
                    continue
                call.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_('ETA H-%(days)s: %(port)s') % {'days': days, 'port': call.port_id.display_name},
                    note=_(
                        'Port call %(port)s (voyage %(voyage)s) ETA %(eta)s (H-%(days)s) '
                        'belum ada ATA. Koordinasi dengan agen/kapal.'
                    ) % {
                        'port': call.port_id.display_name, 'voyage': call.voyage_id.name,
                        'eta': call.eta, 'days': days,
                    },
                    user_id=call.voyage_id.user_id.id or self.env.uid,
                )
                if template and call.agent_id and call.agent_id.email:
                    try:
                        template.send_mail(call.id, force_send=True, raise_exception=False)
                    except Exception as e:
                        _logger.warning('Gagal kirim email ETA reminder untuk port call %s: %s', call.id, e)

    @api.model
    def _cron_clearance_pending_alert(self):
        """Harian — clearance_line_ids status pending/submitted >2 hari sejak atb."""
        cutoff = fields.Datetime.now() - timedelta(days=2)
        calls = self.search([('atb', '!=', False), ('atb', '<=', cutoff)])
        for call in calls:
            pending_lines = call.clearance_line_ids.filtered(
                lambda line: line.status in ('pending', 'submitted')
            )
            if not pending_lines:
                continue
            existing = self.env['mail.activity'].search([
                ('res_model', '=', 'vessel.port.call'),
                ('res_id', '=', call.id),
                ('summary', 'like', 'Clearance pending'),
            ])
            if existing:
                continue
            call.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Clearance pending >2 hari — %s') % call.port_id.display_name,
                note=_(
                    'Port call %(port)s (voyage %(voyage)s): %(count)s dokumen clearance '
                    'masih pending/submitted lebih dari 2 hari sejak ATB.'
                ) % {
                    'port': call.port_id.display_name, 'voyage': call.voyage_id.name,
                    'count': len(pending_lines),
                },
                user_id=call.voyage_id.user_id.id or self.env.uid,
            )
