# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

FUEL_TYPE = [
    ('fo', 'FO'),
    ('do', 'DO'),
]

STATE = [
    ('draft', 'Draft'),
    ('reviewed', 'Reviewed'),
    ('flagged', 'Flagged'),
]

# Mapping fuel_type (fo/do) -> xmlid fleet.fuel.type mfo/hsd,mgo untuk query supply
# & consumption (konsisten dengan mapping FO/DO di vessel_bunker_inquiry Sprint 23).
FUEL_TYPE_CODE_MAP = {'fo': ['MFO'], 'do': ['HSD', 'MGO']}


class VesselBunkerRobReconciliation(models.Model):
    _name = 'vessel.bunker.rob.reconciliation'
    _description = 'ROB Reconciliation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'noon_report_end_id desc'

    voyage_id = fields.Many2one('vessel.voyage', string='Voyage', required=True)
    noon_report_start_id = fields.Many2one(
        'vessel.noon.report', string='Noon Report Awal (T1)', required=True,
    )
    noon_report_end_id = fields.Many2one(
        'vessel.noon.report', string='Noon Report Akhir (T2)', required=True,
    )
    fuel_type = fields.Selection(FUEL_TYPE, required=True, default='fo')
    previous_rob = fields.Float(string='Previous ROB (MT)', compute='_compute_rob_values', store=True)
    actual_rob = fields.Float(string='Actual ROB (MT)', compute='_compute_rob_values', store=True)
    total_supply = fields.Float(string='Total Supply (MT)', compute='_compute_total_supply', store=True)
    total_consumption = fields.Float(
        string='Total Consumption (MT)', compute='_compute_total_consumption', store=True,
        help='Dari fleet_fuel_log.qty_liters, dikonversi ke MT dengan asumsi densitas '
             '~1 (1 L ≈ 1 kg) — pendekatan, bukan konversi presisi per jenis BBM. '
             'Refinement densitas per fuel_type ada di Fase 2.',
    )
    expected_rob = fields.Float(
        string='Expected ROB (MT)', compute='_compute_expected_rob', store=True,
    )
    variance = fields.Float(string='Variance (MT)', compute='_compute_variance', store=True)
    variance_pct = fields.Float(string='Variance (%)', compute='_compute_variance', store=True)
    threshold_pct = fields.Float(
        string='Threshold (%)', compute='_compute_threshold_pct', store=True, readonly=False,
    )
    is_anomaly = fields.Boolean(string='Anomaly?', compute='_compute_variance', store=True)
    state = fields.Selection(STATE, default='draft', required=True, tracking=True)
    review_notes = fields.Html()
    vessel_id = fields.Many2one(
        'fleet.vehicle', string='Kapal', related='voyage_id.vessel_id', store=True, readonly=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Perusahaan', required=True,
        default=lambda self: self.env.company,
    )

    _unique_reconciliation = models.Constraint(
        'UNIQUE(voyage_id, noon_report_start_id, noon_report_end_id, fuel_type)',
        'Rekonsiliasi untuk pasangan noon report dan jenis bahan bakar ini sudah ada.',
    )

    @api.constrains('noon_report_start_id', 'noon_report_end_id', 'voyage_id')
    def _check_noon_report_order_and_voyage(self):
        for rec in self:
            start, end = rec.noon_report_start_id, rec.noon_report_end_id
            if end.report_datetime <= start.report_datetime:
                raise ValidationError(_(
                    'Noon Report Akhir harus setelah Noon Report Awal.'
                ))
            if start.voyage_id != rec.voyage_id or end.voyage_id != rec.voyage_id:
                raise ValidationError(_(
                    'Kedua Noon Report harus milik voyage yang sama dengan rekonsiliasi ini.'
                ))

    @api.depends('noon_report_start_id', 'noon_report_end_id', 'fuel_type')
    def _compute_rob_values(self):
        for rec in self:
            field_name = 'rob_%s' % rec.fuel_type
            rec.previous_rob = rec.noon_report_start_id[field_name] if rec.noon_report_start_id else 0.0
            rec.actual_rob = rec.noon_report_end_id[field_name] if rec.noon_report_end_id else 0.0

    @api.depends('voyage_id', 'fuel_type', 'noon_report_start_id.report_datetime',
                 'noon_report_end_id.report_datetime')
    def _compute_total_supply(self):
        for rec in self:
            if not (rec.voyage_id and rec.noon_report_start_id and rec.noon_report_end_id):
                rec.total_supply = 0.0
                continue
            deliveries = self.env['vessel.bunker.delivery'].search([
                ('inquiry_id.voyage_id', '=', rec.voyage_id.id),
                ('state', '=', 'confirmed'),
                ('delivery_datetime', '>=', rec.noon_report_start_id.report_datetime),
                ('delivery_datetime', '<=', rec.noon_report_end_id.report_datetime),
            ])
            codes = FUEL_TYPE_CODE_MAP.get(rec.fuel_type, [])
            deliveries = deliveries.filtered(lambda d: d.fuel_type_id.code in codes)
            rec.total_supply = sum(deliveries.mapped('qty_confirmed_mt'))

    @api.depends('voyage_id', 'fuel_type', 'noon_report_start_id.report_datetime',
                 'noon_report_end_id.report_datetime')
    def _compute_total_consumption(self):
        for rec in self:
            if not (rec.voyage_id and rec.voyage_id.fleet_trip_id
                    and rec.noon_report_start_id and rec.noon_report_end_id):
                rec.total_consumption = 0.0
                continue
            codes = FUEL_TYPE_CODE_MAP.get(rec.fuel_type, [])
            logs = self.env['fleet.fuel.log'].search([
                ('trip_id', '=', rec.voyage_id.fleet_trip_id.id),
                ('state', 'in', ('approved', 'posted')),
                ('fuel_type_id.code', 'in', codes),
                ('date', '>=', rec.noon_report_start_id.report_datetime.date()),
                ('date', '<=', rec.noon_report_end_id.report_datetime.date()),
            ])
            rec.total_consumption = sum(logs.mapped('qty_liters')) / 1000.0

    @api.depends('previous_rob', 'total_supply', 'total_consumption')
    def _compute_expected_rob(self):
        for rec in self:
            rec.expected_rob = rec.previous_rob + rec.total_supply - rec.total_consumption

    @api.depends('vessel_id.bunker_variance_threshold_pct')
    def _compute_threshold_pct(self):
        for rec in self:
            rec.threshold_pct = (
                rec.vessel_id.bunker_variance_threshold_pct
                or rec.company_id.default_bunker_variance_threshold_pct
            )

    @api.depends('actual_rob', 'expected_rob', 'threshold_pct')
    def _compute_variance(self):
        for rec in self:
            rec.variance = rec.actual_rob - rec.expected_rob
            rec.variance_pct = (
                (rec.variance / rec.expected_rob) * 100.0 if rec.expected_rob else 0.0
            )
            rec.is_anomaly = abs(rec.variance_pct) > rec.threshold_pct

    def action_review(self):
        for rec in self:
            rec.state = 'reviewed'

    def action_flag(self):
        for rec in self:
            rec.state = 'flagged'

    @api.model
    def _cron_generate_rob_reconciliation(self):
        """§4.3/§4.5 — harian, auto-create record untuk pasangan noon report approved
        berurutan pada voyage sailing/at_port yang belum punya reconciliation. Kirim
        activity ke Operations kalau is_anomaly=True (melengkapi anomaly detection
        consumption-based fleet_fuel_log yang sudah ada, bukan menggantikan)."""
        voyages = self.env['vessel.voyage'].search([('state', 'in', ('sailing', 'at_port'))])
        ops_group = self.env.ref('vessel_voyage_operations.group_voyage_ops_user', raise_if_not_found=False)
        for voyage in voyages:
            reports = self.env['vessel.noon.report'].search([
                ('voyage_id', '=', voyage.id), ('state', '=', 'approved'),
            ], order='report_datetime asc')
            for i in range(len(reports) - 1):
                start, end = reports[i], reports[i + 1]
                for fuel_type in ('fo', 'do'):
                    existing = self.search([
                        ('voyage_id', '=', voyage.id),
                        ('noon_report_start_id', '=', start.id),
                        ('noon_report_end_id', '=', end.id),
                        ('fuel_type', '=', fuel_type),
                    ], limit=1)
                    if existing:
                        continue
                    rec = self.create({
                        'voyage_id': voyage.id,
                        'noon_report_start_id': start.id,
                        'noon_report_end_id': end.id,
                        'fuel_type': fuel_type,
                    })
                    if rec.is_anomaly and ops_group:
                        for user in ops_group.user_ids:
                            rec.activity_schedule(
                                'mail.mail_activity_data_todo',
                                summary=_('ROB Anomaly Terdeteksi: %s') % rec.vessel_id.name,
                                note=_(
                                    'Variance %(pct).1f%% (expected %(exp).1f MT, actual '
                                    '%(act).1f MT) melebihi threshold %(th).1f%%.'
                                ) % {
                                    'pct': rec.variance_pct, 'exp': rec.expected_rob,
                                    'act': rec.actual_rob, 'th': rec.threshold_pct,
                                },
                                user_id=user.id,
                            )

    @api.model
    def _demo_setup_rob_scenario(self):
        """§10.5 acceptance criteria persis — previous ROB 200, supply 495 (delivery
        Sprint 24), consumption 150 -> expected 545, actual 500 -> variance -45,
        is_anomaly=True (default threshold 8%, variance_pct ~8.26%).

        vessel_voyage_pnl TIDAK jadi dependency modul ini (§12.3 tech spec) — trip +
        fuel log dibuat sendiri di sini (bukan mengandalkan demo vessel_voyage_pnl
        yang mungkin tidak terinstall), meski polanya mirip."""
        inquiry = self.env.ref('vessel_bunker_management.demo_bunker_inquiry_1', raise_if_not_found=False)
        voyage = self.env.ref('vessel_voyage_operations.demo_voyage_3', raise_if_not_found=False)
        if not inquiry or not voyage:
            return
        if not inquiry.voyage_id:
            inquiry.voyage_id = voyage.id

        now = fields.Datetime.now()
        report_start = self.env['vessel.noon.report'].search([
            ('voyage_id', '=', voyage.id), ('rob_fo', '=', 200),
        ], limit=1)
        if not report_start:
            report_start = self.env['vessel.noon.report'].create({
                'voyage_id': voyage.id,
                'report_datetime': now - timedelta(days=2),
                'rob_fo': 200,
                'rob_do': 20,
                'state': 'approved',
            })
        report_end = self.env['vessel.noon.report'].search([
            ('voyage_id', '=', voyage.id), ('rob_fo', '=', 500),
        ], limit=1)
        if not report_end:
            report_end = self.env['vessel.noon.report'].create({
                'voyage_id': voyage.id,
                'report_datetime': now + timedelta(days=1),
                'rob_fo': 500,
                'rob_do': 15,
                'state': 'approved',
            })

        if not voyage.fleet_trip_id:
            trip = self.env['fleet.vehicle.trip'].create({
                'name': _('Demo Trip (Bunker) — %s') % voyage.name,
                'vehicle_id': voyage.vessel_id.id,
                'departure_date': voyage.date_departure or now,
                'arrival_date': voyage.date_arrival_final or now,
                'state': 'done',
            })
            voyage.fleet_trip_id = trip.id
        mfo_type = self.env.ref('fleet_fuel_log.fuel_type_mfo')
        if voyage.fleet_trip_id and not self.env['fleet.fuel.log'].search([
            ('trip_id', '=', voyage.fleet_trip_id.id), ('fuel_type_id', '=', mfo_type.id),
        ]):
            # Guard cek fuel_type_id spesifik (bukan "ada fuel log apapun untuk trip
            # ini") — trip yang sama bisa punya beberapa entri fuel log fuel_type
            # berbeda (mis. dari demo module lain di database dev yang sama).
            self.env['fleet.fuel.log'].create({
                'vehicle_id': voyage.vessel_id.id,
                'trip_id': voyage.fleet_trip_id.id,
                'fuel_type_id': mfo_type.id,
                'transaction_type': 'trip',
                'date': fields.Date.context_today(self),
                'qty_liters': 150000,
                'price_per_liter': 1.2,
                'state': 'approved',
            })

        existing = self.search([
            ('voyage_id', '=', voyage.id),
            ('noon_report_start_id', '=', report_start.id),
            ('noon_report_end_id', '=', report_end.id),
            ('fuel_type', '=', 'fo'),
        ], limit=1)
        if not existing:
            self.create({
                'voyage_id': voyage.id,
                'noon_report_start_id': report_start.id,
                'noon_report_end_id': report_end.id,
                'fuel_type': 'fo',
            })
