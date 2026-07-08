# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class VesselSofLine(models.Model):
    _name = 'vessel.sof.line'
    _description = 'Statement of Facts Line'
    _order = 'datetime_start'

    laytime_id = fields.Many2one(
        'vessel.laytime.calculation', string='Laytime Calculation',
        required=True, ondelete='cascade', index=True,
    )
    datetime_start = fields.Datetime(string='Mulai', required=True)
    datetime_end = fields.Datetime(string='Selesai', required=True)
    duration_hours = fields.Float(
        string='Durasi (jam)', compute='_compute_duration_hours', store=True,
    )
    activity = fields.Char(string='Aktivitas', help='Misal: "Commenced loading", "Rain stop", ...')
    interruption_type_id = fields.Many2one(
        'vessel.laytime.interruption.type', string='Tipe Interupsi',
        help='Kosongkan jika ini periode counting normal (bukan interupsi).',
    )
    is_counting = fields.Boolean(
        string='Counting', compute='_compute_is_counting', store=True,
        help='True jika periode ini dihitung sebagai laytime (tidak ada interupsi, '
             'atau interupsi yang is_counting=True).',
    )
    remarks = fields.Char(string='Keterangan')

    @api.depends('laytime_id.display_name', 'datetime_start', 'activity')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('%(laytime)s — %(activity)s (%(start)s)') % {
                'laytime': rec.laytime_id.display_name or _('Laytime'),
                'activity': rec.activity or _('SOF'),
                'start': rec.datetime_start or '?',
            }

    @api.depends('datetime_start', 'datetime_end')
    def _compute_duration_hours(self):
        for rec in self:
            if rec.datetime_start and rec.datetime_end:
                delta = rec.datetime_end - rec.datetime_start
                rec.duration_hours = delta.total_seconds() / 3600.0
            else:
                rec.duration_hours = 0.0

    @api.depends('interruption_type_id', 'interruption_type_id.is_counting')
    def _compute_is_counting(self):
        for rec in self:
            if rec.interruption_type_id:
                rec.is_counting = rec.interruption_type_id.is_counting
            else:
                rec.is_counting = True

    @api.constrains('datetime_start', 'datetime_end')
    def _check_dates(self):
        for rec in self:
            if rec.datetime_start and rec.datetime_end and rec.datetime_end <= rec.datetime_start:
                raise ValidationError(_(
                    'Waktu selesai harus setelah waktu mulai (SOF line: %s).'
                ) % (rec.activity or rec.id))

    def _check_overlap_warning(self):
        """Warning (bukan blokir) jika ada SOF line overlap dalam satu laytime —
        SOF nyata di lapangan kadang paralel (misal shifting bersamaan cuaca buruk)."""
        for laytime in self.mapped('laytime_id'):
            lines = laytime.sof_line_ids.sorted('datetime_start')
            for i in range(len(lines) - 1):
                if lines[i].datetime_end > lines[i + 1].datetime_start:
                    laytime.message_post(body=_(
                        '⚠️ Peringatan: SOF line "%(a)s" dan "%(b)s" waktunya beririsan.'
                    ) % {'a': lines[i].activity or lines[i].id, 'b': lines[i + 1].activity or lines[i + 1].id})

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._check_overlap_warning()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if 'datetime_start' in vals or 'datetime_end' in vals:
            self._check_overlap_warning()
        return res
