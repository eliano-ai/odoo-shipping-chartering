# -*- coding: utf-8 -*-
from odoo import fields, models, _


class VesselPnlBulkGenerateWizard(models.TransientModel):
    _name = 'vessel.pnl.bulk.generate.wizard'
    _description = 'Generate P&L Massal (Historical Backfill)'

    date_from = fields.Date(
        string='Dari Tanggal Berangkat',
        help='Kosongkan untuk tidak membatasi tanggal awal.',
    )
    date_to = fields.Date(
        string='Sampai Tanggal Berangkat',
        help='Kosongkan untuk tidak membatasi tanggal akhir.',
    )

    def action_generate(self):
        self.ensure_one()
        domain = [('state', '=', 'completed'), ('pnl_id', '=', False)]
        if self.date_from:
            domain.append(('date_departure', '>=', self.date_from))
        if self.date_to:
            domain.append(('date_departure', '<=', self.date_to))
        voyages = self.env['vessel.voyage'].search(domain)

        VoyagePnl = self.env['vessel.voyage.pnl']
        generated = VoyagePnl.browse()
        for voyage in voyages:
            pnl = VoyagePnl.create({'voyage_id': voyage.id})
            pnl.action_generate_pnl()
            generated |= pnl

        message = _('%(count)s Voyage P&L berhasil di-generate.') % {'count': len(generated)}
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Generate P&L Massal Selesai'),
                'message': message,
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': _('Voyage P&L Ter-generate'),
                    'res_model': 'vessel.voyage.pnl',
                    'view_mode': 'list,form',
                    'domain': [('id', 'in', generated.ids)],
                } if generated else {'type': 'ir.actions.act_window_close'},
            },
        }
