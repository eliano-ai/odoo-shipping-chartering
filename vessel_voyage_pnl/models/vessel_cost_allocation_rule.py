# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

ALLOCATION_METHOD = [
    ('per_voyage_day', 'Per Voyage Day'),
    ('per_calendar_day', 'Per Calendar Day'),
    ('equal_split', 'Equal Split'),
    ('fixed_percentage', 'Fixed Percentage'),
    ('manual', 'Manual'),
]


class VesselCostAllocationRule(models.Model):
    _name = 'vessel.cost.allocation.rule'
    _description = 'Aturan Alokasi Biaya Tidak Langsung'
    _order = 'cost_category_id'

    cost_category_id = fields.Many2one(
        'vessel.pnl.cost.category', string='Kategori Biaya', required=True,
        domain=[('category_group', '=', 'allocated_cost')],
    )
    allocation_method = fields.Selection(ALLOCATION_METHOD, required=True, default='manual')
    fixed_percentage_value = fields.Float(
        string='Persentase Tetap (%)',
        help='Terisi jika allocation_method = Fixed Percentage.',
    )
    active = fields.Boolean(default=True)

    @api.depends('cost_category_id.name', 'allocation_method')
    def _compute_display_name(self):
        labels = dict(ALLOCATION_METHOD)
        for rec in self:
            rec.display_name = _('%(cat)s — %(method)s') % {
                'cat': rec.cost_category_id.name or _('Kategori'),
                'method': labels.get(rec.allocation_method, rec.allocation_method or ''),
            }

    @api.constrains('cost_category_id', 'active')
    def _check_one_active_rule_per_category(self):
        for rec in self:
            if not rec.active:
                continue
            duplicate = self.search([
                ('id', '!=', rec.id),
                ('cost_category_id', '=', rec.cost_category_id.id),
                ('active', '=', True),
            ])
            if duplicate:
                raise ValidationError(_(
                    'Sudah ada aturan alokasi aktif untuk kategori biaya "%s". '
                    'Nonaktifkan aturan lama sebelum membuat yang baru.'
                ) % rec.cost_category_id.name)
