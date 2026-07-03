# -*- coding: utf-8 -*-
from odoo import fields, models


class VesselDisbursementItemType(models.Model):
    _name = 'vessel.disbursement.item.type'
    _description = 'Tipe Item Disbursement Pelabuhan (PDA/FDA)'
    _order = 'name'

    name = fields.Char(string='Nama', required=True, translate=True)
    active = fields.Boolean(default=True)
