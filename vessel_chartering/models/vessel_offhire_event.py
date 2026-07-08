# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


OFFHIRE_REASON = [
    ('breakdown', 'Breakdown'),
    ('drydock', 'Drydock'),
    ('crew', 'Crew'),
    ('deficiency', 'Deficiency'),
    ('other', 'Lainnya'),
]


class VesselOffhireEvent(models.Model):
    _name = 'vessel.offhire.event'
    _description = 'Off-hire Event (Time Charter)'
    _order = 'datetime_start'

    contract_id = fields.Many2one(
        'vessel.charter.contract', string='Kontrak',
        required=True, ondelete='cascade', index=True,
        domain=[('contract_type', '=', 'time')],
    )
    datetime_start = fields.Datetime(string='Mulai', required=True)
    datetime_end = fields.Datetime(string='Selesai', required=True)
    duration_hours = fields.Float(
        string='Durasi (jam)', compute='_compute_duration_hours', store=True,
    )
    reason = fields.Selection(OFFHIRE_REASON, string='Alasan', required=True, default='breakdown')
    description = fields.Char(string='Keterangan')
    fuel_deduction = fields.Monetary(
        string='Bunker Deduction', currency_field='currency_id',
        help='Biaya bunker selama off-hire yang ditanggung owner.',
    )
    currency_id = fields.Many2one(
        related='contract_id.currency_id', string='Currency', readonly=True,
    )

    @api.depends('contract_id.name', 'reason', 'datetime_start')
    def _compute_display_name(self):
        labels = dict(OFFHIRE_REASON)
        for rec in self:
            rec.display_name = _('%(contract)s — Off-hire %(reason)s (%(date)s)') % {
                'contract': rec.contract_id.name or _('Kontrak'),
                'reason': labels.get(rec.reason, rec.reason or ''),
                'date': rec.datetime_start or '?',
            }

    @api.depends('datetime_start', 'datetime_end')
    def _compute_duration_hours(self):
        for rec in self:
            if rec.datetime_start and rec.datetime_end:
                delta = rec.datetime_end - rec.datetime_start
                rec.duration_hours = delta.total_seconds() / 3600.0
            else:
                rec.duration_hours = 0.0

    @api.constrains('datetime_start', 'datetime_end')
    def _check_dates(self):
        for rec in self:
            if rec.datetime_start and rec.datetime_end and rec.datetime_end <= rec.datetime_start:
                raise ValidationError(_(
                    'Waktu selesai off-hire harus setelah waktu mulai.'
                ))
