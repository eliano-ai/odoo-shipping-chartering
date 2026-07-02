# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


class FleetMaintenanceSchedule(models.Model):
    _name = 'fleet.maintenance.schedule'
    _description = 'Fleet Maintenance Schedule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'scheduled_date asc, id desc'
    _rec_name = 'name'

    # ─── Identity ────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Reference',
        required=True,
        readonly=True,
        default=lambda self: _('New'),
        copy=False,
        tracking=True,
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
        ondelete='cascade',
        tracking=True,
        index=True,
    )
    vehicle_license_plate = fields.Char(
        related='vehicle_id.license_plate',
        string='License Plate',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    # ─── Type & Description ──────────────────────────────────────────────────
    maintenance_type = fields.Selection(
        selection=[
            ('preventive', 'Preventive'),
            ('corrective', 'Corrective'),
            ('predictive', 'Predictive'),
            ('overhaul', 'Overhaul'),
        ],
        string='Maintenance Type',
        required=True,
        default='preventive',
        tracking=True,
    )
    description = fields.Text(
        string='Description / Work Order',
    )
    notes = fields.Html(
        string='Internal Notes',
    )

    # ─── Schedule Trigger ────────────────────────────────────────────────────
    schedule_basis = fields.Selection(
        selection=[
            ('date', 'Date (Time-based)'),
            ('odometer', 'Odometer / Engine Hours'),
            ('both', 'Date & Odometer'),
        ],
        string='Schedule Basis',
        required=True,
        default='both',
        tracking=True,
    )
    scheduled_date = fields.Date(
        string='Scheduled Date',
        tracking=True,
        index=True,
    )
    completed_date = fields.Date(
        string='Completion Date',
        readonly=True,
        tracking=True,
    )
    odometer_trigger = fields.Float(
        string='Odometer Trigger (km)',
        digits=(10, 2),
        help='Maintenance will be triggered when vehicle odometer reaches this value.',
    )
    odometer_unit = fields.Selection(
        related='vehicle_id.odometer_unit',
        string='Odometer Unit',
        readonly=True,
    )
    current_odometer = fields.Float(
        string='Current Odometer',
        compute='_compute_current_odometer',
        store=False,
    )
    reminder_days = fields.Integer(
        string='Reminder (days before)',
        default=7,
        help='Send reminder email this many days before the scheduled date.',
    )
    reminder_sent = fields.Boolean(
        string='Reminder Sent',
        default=False,
        copy=False,
    )

    # ─── Responsible ─────────────────────────────────────────────────────────
    # FIX #3: Hapus ref() dari domain di Python model definition
    # Domain filter dipindahkan ke view XML
    technician_id = fields.Many2one(
        'res.users',
        string='Assigned Technician',
        tracking=True,
    )
    fleet_manager_id = fields.Many2one(
        'res.users',
        string='Fleet Manager',
        default=lambda self: self.env.user,
        tracking=True,
    )

    # ─── Cost ────────────────────────────────────────────────────────────────
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    estimated_cost = fields.Monetary(
        string='Estimated Cost',
        currency_field='currency_id',
    )
    actual_cost = fields.Monetary(
        string='Actual Cost',
        currency_field='currency_id',
        compute='_compute_actual_cost',
        store=True,
    )

    # ─── Spare Parts (O2M) ───────────────────────────────────────────────────
    part_ids = fields.One2many(
        'fleet.maintenance.part',
        'schedule_id',
        string='Spare Parts',
        copy=True,
    )
    parts_count = fields.Integer(
        string='Parts Count',
        compute='_compute_parts_count',
    )

    # ─── Integration Fields ──────────────────────────────────────────────────
    maintenance_request_id = fields.Many2one(
        'maintenance.request',
        string='Maintenance Request',
        readonly=True,
        copy=False,
        tracking=True,
    )
    stock_picking_id = fields.Many2one(
        'stock.picking',
        string='Stock Picking (Parts)',
        readonly=True,
        copy=False,
    )

    # ─── State Machine ───────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('in_progress', 'In Progress'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        readonly=True,
        copy=False,
        tracking=True,
        index=True,
    )

    # ─── Computed ────────────────────────────────────────────────────────────
    @api.depends('vehicle_id')
    def _compute_current_odometer(self):
        for rec in self:
            rec.current_odometer = rec.vehicle_id.odometer if rec.vehicle_id else 0.0

    @api.depends('part_ids.subtotal_cost')
    def _compute_actual_cost(self):
        for rec in self:
            rec.actual_cost = sum(rec.part_ids.mapped('subtotal_cost'))

    @api.depends('part_ids')
    def _compute_parts_count(self):
        for rec in self:
            rec.parts_count = len(rec.part_ids)

    # ─── Onchange ────────────────────────────────────────────────────────────
    @api.onchange('schedule_basis')
    def _onchange_schedule_basis(self):
        if self.schedule_basis == 'odometer':
            self.scheduled_date = False
        elif self.schedule_basis == 'date':
            self.odometer_trigger = 0.0

    # ─── Constraints ─────────────────────────────────────────────────────────
    @api.constrains('scheduled_date', 'odometer_trigger', 'schedule_basis')
    def _check_schedule_fields(self):
        for rec in self:
            if rec.schedule_basis in ('date', 'both') and not rec.scheduled_date:
                raise ValidationError(_('Scheduled Date is required when basis is Date or Both.'))
            if rec.schedule_basis in ('odometer', 'both') and not rec.odometer_trigger:
                raise ValidationError(_('Odometer Trigger is required when basis is Odometer or Both.'))

    # ─── ORM Overrides ───────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'fleet.maintenance.schedule') or _('New')
        return super().create(vals_list)

    # ─── State Actions ───────────────────────────────────────────────────────
    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only Draft schedules can be confirmed.'))
            rec._create_maintenance_request()
            rec._schedule_reminder_activity()
            rec.state = 'confirmed'
            rec.message_post(
                body=_('Schedule confirmed. Maintenance Request created: <b>%s</b>') % (
                    rec.maintenance_request_id.name if rec.maintenance_request_id else '-'
                )
            )

    def action_start(self):
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(_('Only Confirmed schedules can be started.'))
            if rec.maintenance_request_id:
                # FIX #5: Guard jika stage tidak ditemukan
                stage = self._get_maintenance_stage('In Progress')
                if stage:
                    rec.maintenance_request_id.stage_id = stage
            rec.state = 'in_progress'
            rec.message_post(body=_('Maintenance work started.'))

    def action_done(self):
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError(_('Only In Progress schedules can be marked as Done.'))
            rec.completed_date = date.today()
            rec._consume_spare_parts()
            if rec.maintenance_request_id:
                # FIX #5: Guard jika stage tidak ditemukan
                done_stage = self._get_maintenance_stage('Done')
                if done_stage:
                    rec.maintenance_request_id.stage_id = done_stage
            rec.state = 'done'
            rec.message_post(
                body=_('Maintenance completed on %s. Actual cost: %s') % (
                    rec.completed_date,
                    rec.currency_id.symbol + ' ' + str(rec.actual_cost),
                )
            )

    def action_cancel(self):
        for rec in self:
            if rec.state == 'done':
                raise UserError(_('Completed maintenance cannot be cancelled.'))
            if rec.maintenance_request_id and \
                    rec.maintenance_request_id.state not in ('done', 'cancel'):
                rec.maintenance_request_id.write({'active': False})
            rec.state = 'cancelled'
            rec.message_post(body=_('Maintenance schedule cancelled.'))

    def action_reset_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_('Only cancelled schedules can be reset to draft.'))
            rec.state = 'draft'
            rec.reminder_sent = False

    # ─── Business Logic ──────────────────────────────────────────────────────
    def _create_maintenance_request(self):
        self.ensure_one()
        if self.maintenance_request_id:
            return
        maintenance_type_map = {
            'preventive': 'preventive',
            'corrective': 'corrective',
            'predictive': 'preventive',
            'overhaul': 'corrective',
        }
        request = self.env['maintenance.request'].create({
            'name': _('[%s] %s - %s') % (
                self.name,
                self.vehicle_id.name,
                dict(self._fields['maintenance_type'].selection).get(self.maintenance_type, ''),
            ),
            'maintenance_type': maintenance_type_map.get(self.maintenance_type, 'preventive'),
            'user_id': self.technician_id.id or self.env.uid,
            'description': self.description or '',
            'schedule_date': self.scheduled_date,
            'company_id': self.company_id.id,
        })
        self.maintenance_request_id = request

    def _schedule_reminder_activity(self):
        self.ensure_one()
        if not self.scheduled_date or not self.reminder_days:
            return
        remind_date = self.scheduled_date - timedelta(days=self.reminder_days)
        if remind_date < date.today():
            remind_date = date.today()
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            return
        self.activity_schedule(
            activity_type_id=activity_type.id,
            date_deadline=remind_date,
            summary=_('Maintenance reminder: %s') % self.name,
            note=_('Scheduled maintenance for vehicle <b>%s</b> on %s.') % (
                self.vehicle_id.name, self.scheduled_date
            ),
            user_id=self.technician_id.id or self.fleet_manager_id.id or self.env.uid,
        )

    def _consume_spare_parts(self):
        self.ensure_one()
        parts = self.part_ids.filtered(lambda p: p.product_id and p.qty_planned > 0)
        if not parts:
            return
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not picking_type:
            _logger.warning('No internal picking type found. Skipping stock consumption.')
            return
        src_location = picking_type.default_location_src_id or self.env.ref(
            'stock.stock_location_stock', raise_if_not_found=False
        )
        dest_location = self.env.ref('stock.stock_location_production', raise_if_not_found=False)
        if not src_location or not dest_location:
            _logger.warning('Source or destination location not found. Skipping stock consumption.')
            return
        move_vals = [(0, 0, {
            'name': part.product_id.name,
            'product_id': part.product_id.id,
            'product_uom_qty': part.qty_planned,
            'product_uom': part.product_id.uom_id.id,
            'location_id': src_location.id,
            'location_dest_id': dest_location.id,
        }) for part in parts]

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': src_location.id,
            'location_dest_id': dest_location.id,
            'origin': self.name,
            'move_ids': move_vals,
            'note': _('Spare parts consumption for maintenance: %s') % self.name,
        })
        picking.action_confirm()
        picking.action_assign()
        self.stock_picking_id = picking

    @api.model
    def _get_maintenance_stage(self, stage_name):
        return self.env['maintenance.stage'].search([
            ('name', 'ilike', stage_name)
        ], limit=1) or False

    # ─── Cron ────────────────────────────────────────────────────────────────
    @api.model
    def _cron_send_maintenance_reminders(self):
        today = date.today()
        schedules = self.search([
            ('state', 'in', ('draft', 'confirmed')),
            ('scheduled_date', '!=', False),
            ('reminder_sent', '=', False),
            ('reminder_days', '>', 0),
        ])
        template = self.env.ref(
            'fleet_maintenance_schedule.email_template_maintenance_reminder',
            raise_if_not_found=False,
        )
        for sched in schedules:
            remind_on = sched.scheduled_date - timedelta(days=sched.reminder_days)
            if remind_on <= today:
                try:
                    if template:
                        template.send_mail(sched.id, force_send=True)
                    sched.reminder_sent = True
                    _logger.info('Reminder sent for schedule %s', sched.name)
                except Exception as e:
                    _logger.error('Failed to send reminder for %s: %s', sched.name, str(e))

    # ─── Smart Button Actions ─────────────────────────────────────────────────
    def action_view_maintenance_request(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'maintenance.request',
            'view_mode': 'form',
            'res_id': self.maintenance_request_id.id,
            'target': 'current',
        }

    def action_view_stock_picking(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.stock_picking_id.id,
            'target': 'current',
        }


class FleetMaintenancePart(models.Model):
    _name = 'fleet.maintenance.part'
    _description = 'Spare Part Line for Maintenance Schedule'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    schedule_id = fields.Many2one(
        'fleet.maintenance.schedule',
        string='Maintenance Schedule',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product (Spare Part)',
        required=True,
        domain="[('type', 'in', ['product', 'consu'])]",
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        related='product_id.uom_id',
        readonly=True,
    )
    qty_planned = fields.Float(
        string='Planned Qty',
        digits='Product Unit of Measure',
        default=1.0,
        required=True,
    )
    qty_used = fields.Float(
        string='Actual Qty Used',
        digits='Product Unit of Measure',
        default=0.0,
    )
    unit_cost = fields.Float(
        string='Unit Cost',
        digits='Product Price',
        compute='_compute_unit_cost',
        store=True,
    )
    
    state = fields.Selection(
        related='schedule_id.state',
        string='Schedule State',
        store=False,
    )
    subtotal_cost = fields.Float(
        string='Subtotal',
        compute='_compute_subtotal_cost',
        store=True,
    )
    note = fields.Char(string='Note')

    @api.depends('product_id')
    def _compute_unit_cost(self):
        for line in self:
            line.unit_cost = line.product_id.standard_price if line.product_id else 0.0

    @api.depends('qty_planned', 'unit_cost')
    def _compute_subtotal_cost(self):
        for line in self:
            line.subtotal_cost = line.qty_planned * line.unit_cost

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.unit_cost = self.product_id.standard_price