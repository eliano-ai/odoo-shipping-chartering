from odoo import api, fields, models


class FleetVehicleCrewInherit(models.Model):
    _inherit = 'fleet.vehicle'

    crew_assignment_ids = fields.One2many(
        'vessel.crew.assignment', 'vehicle_id',
        string='Riwayat Penugasan ABK',
    )
    active_crew_ids = fields.Many2many(
        'vessel.seafarer',
        compute='_compute_active_crew',
        string='ABK Aktif',
    )
    active_crew_count = fields.Integer(
        compute='_compute_active_crew',
        string='Jumlah ABK di Kapal',
    )
    crew_schedule_ids = fields.One2many(
        'vessel.crew.schedule', 'vehicle_id',
        string='Jadwal Crew',
    )

    def _compute_active_crew(self):
        Assignment = self.env['vessel.crew.assignment']
        for vessel in self:
            if not vessel.is_vessel:
                vessel.active_crew_ids = False
                vessel.active_crew_count = 0
                continue
            active = Assignment.search([
                ('vehicle_id', '=', vessel.id),
                ('state', '=', 'on_board'),
            ])
            seafarers = active.mapped('seafarer_id')
            vessel.active_crew_ids = seafarers
            vessel.active_crew_count = len(seafarers)

    def action_view_active_crew(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Manning List — {self.name}',
            'res_model': 'vessel.crew.assignment',
            'view_mode': 'list,form',
            'domain': [
                ('vehicle_id', '=', self.id),
                ('state', '=', 'on_board'),
            ],
        }

    def action_view_crew_schedule(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Jadwal Crew — {self.name}',
            'res_model': 'vessel.crew.schedule',
            'view_mode': 'list,form,calendar',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id},
        }
