# -*- coding: utf-8 -*-
from odoo import fields, models


class VesselDelayType(models.Model):
    _name = 'vessel.delay.type'
    _description = 'Tipe Delay/Event Voyage'
    _order = 'name'

    name = fields.Char(string='Nama', required=True, translate=True)
    active = fields.Boolean(default=True)
