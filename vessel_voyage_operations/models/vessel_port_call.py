# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

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
    notes = fields.Html(string='Catatan')
    company_id = fields.Many2one(
        related='voyage_id.company_id', string='Perusahaan', store=True, readonly=True,
    )

    @api.depends('cargo_ops_commenced', 'cargo_ops_completed')
    def _compute_cargo_ops_rate_mt_day(self):
        # Placeholder — akan depend ke qty dari cargo_document_ids setelah
        # vessel.cargo.document ada (Sprint 12).
        for rec in self:
            rec.cargo_ops_rate_mt_day = 0.0

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
