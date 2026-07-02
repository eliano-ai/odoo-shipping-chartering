# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import date
import logging

_logger = logging.getLogger(__name__)


class FleetFuelLog(models.Model):
    _name = 'fleet.fuel.log'
    _description = 'Fleet Fuel Log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
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
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        index=True,
    )

    # ─── Vehicle & Fuel ──────────────────────────────────────────────────────
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    vehicle_license_plate = fields.Char(
        related='vehicle_id.license_plate',
        store=True,
        readonly=True,
    )
    fuel_type_id = fields.Many2one(
        'fleet.fuel.type',
        string='Fuel Type',
        required=True,
        tracking=True,
    )
    transaction_type = fields.Selection(
        selection=[
            ('refuel', 'Refueling (SPBU / Bunker)'),
            ('daily', 'Daily Consumption'),
            ('trip', 'Per Trip / Voyage'),
        ],
        string='Transaction Type',
        required=True,
        default='refuel',
        tracking=True,
    )

    # ─── Odometer ────────────────────────────────────────────────────────────
    odometer_start = fields.Float(
        string='Odometer Start',
        digits=(10, 2),
    )
    odometer_end = fields.Float(
        string='Odometer End',
        digits=(10, 2),
    )
    odometer_unit = fields.Selection(
        related='vehicle_id.odometer_unit',
        readonly=True,
    )
    distance = fields.Float(
        string='Distance',
        compute='_compute_distance',
        store=True,
        digits=(10, 2),
    )

    # ─── Fuel Quantity & Cost ─────────────────────────────────────────────────
    qty_liters = fields.Float(
        string='Quantity (Liters)',
        required=True,
        digits=(10, 3),
        tracking=True,
    )
    price_per_liter = fields.Float(
        string='Price / Liter',
        digits='Product Price',
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )
    total_cost = fields.Monetary(
        string='Total Cost',
        compute='_compute_total_cost',
        store=True,
        currency_field='currency_id',
        tracking=True,
    )

    # ─── Consumption Analytics ───────────────────────────────────────────────
    consumption_rate = fields.Float(
        string='Consumption (L/100km)',
        compute='_compute_consumption_rate',
        store=True,
        digits=(10, 3),
        help='Liter per 100 km. Hanya valid untuk tipe Daily/Trip dengan odometer.',
    )
    consumption_per_hour = fields.Float(
        string='Consumption (L/hour)',
        digits=(10, 3),
        help='Untuk mesin kapal/MFO: isi manual atau hitung dari jam operasi.',
    )
    engine_hours = fields.Float(
        string='Engine Hours',
        digits=(10, 2),
        help='Jam operasi mesin (untuk MFO/kapal).',
    )

    # ─── Anomaly ─────────────────────────────────────────────────────────────
    is_anomaly = fields.Boolean(
        string='Anomaly Detected',
        compute='_compute_is_anomaly',
        store=True,
        tracking=True,
    )
    anomaly_reason = fields.Char(
        string='Anomaly Reason',
        readonly=True,
    )
    anomaly_notified = fields.Boolean(
        string='Manager Notified',
        default=False,
        copy=False,
    )

    # ─── Trip Link ───────────────────────────────────────────────────────────
    trip_id = fields.Many2one(
        'fleet.vehicle.trip',
        string='Trip / Voyage',
        domain="[('vehicle_id', '=', vehicle_id)]",
        ondelete='set null',
        index=True,
    )

    # ─── Responsible ─────────────────────────────────────────────────────────
    driver_id = fields.Many2one(
        'res.partner',
        string='Driver / Operator',
        related='vehicle_id.driver_id',
        readonly=True,
        store=True,
    )
    logged_by = fields.Many2one(
        'res.users',
        string='Logged By',
        default=lambda self: self.env.user,
        readonly=True,
    )
    fleet_manager_id = fields.Many2one(
        'res.users',
        string='Fleet Manager',
        domain="[('active', '=', True), ('share', '=', False)]",
    )

    # ─── Location ────────────────────────────────────────────────────────────
    location_name = fields.Char(
        string='Station / Port Name',
        help='Nama SPBU, pelabuhan, atau bunker station.',
    )
    note = fields.Text(string='Notes')

    # ─── Integration: Inventory ──────────────────────────────────────────────
    stock_move_id = fields.Many2one(
        'stock.move',
        string='Stock Move',
        readonly=True,
        copy=False,
    )

    # ─── Integration: Accounting ─────────────────────────────────────────────
    account_move_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        readonly=True,
        copy=False,
        tracking=True,
    )

    # ─── State ───────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('to_approve', 'To Approve'),
            ('approved', 'Approved'),
            ('posted', 'Posted'),
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
    
    is_fleet_manager = fields.Boolean(
        compute='_compute_ui_flags',
    )
    is_multi_company = fields.Boolean(
        compute='_compute_ui_flags',
    )
    
    def _compute_ui_flags(self):
        is_mgr = self.env.user.has_group('fleet_fuel_log.group_fleet_manager')
        is_mc = self.env.user.has_group('base.group_multi_company')
        for rec in self:
            rec.is_fleet_manager = is_mgr
            rec.is_multi_company = is_mc

    # ─── Computed ────────────────────────────────────────────────────────────
    @api.depends('odometer_start', 'odometer_end')
    def _compute_distance(self):
        for rec in self:
            if rec.odometer_end and rec.odometer_start:
                rec.distance = max(0.0, rec.odometer_end - rec.odometer_start)
            else:
                rec.distance = 0.0

    @api.depends('qty_liters', 'price_per_liter')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = rec.qty_liters * rec.price_per_liter

    @api.depends('qty_liters', 'distance')
    def _compute_consumption_rate(self):
        for rec in self:
            if rec.distance and rec.distance > 0 and rec.qty_liters:
                rec.consumption_rate = (rec.qty_liters / rec.distance) * 100.0
            else:
                rec.consumption_rate = 0.0

    @api.depends('consumption_rate', 'vehicle_id', 'fuel_type_id', 'qty_liters')
    def _compute_is_anomaly(self):
        for rec in self:
            rec.is_anomaly = False
            rec.anomaly_reason = False
            if not rec.vehicle_id or not rec.fuel_type_id:
                continue
            threshold_pct = rec.fuel_type_id.anomaly_threshold_pct or 30.0

            # Anomali berbasis L/100km (untuk kendaraan darat)
            if rec.consumption_rate > 0:
                avg = rec._get_vehicle_avg_consumption()
                if avg and avg > 0:
                    if rec.consumption_rate > avg * (1 + threshold_pct / 100.0):
                        rec.is_anomaly = True
                        rec.anomaly_reason = _(
                            'Consumption %.2f L/100km exceeds avg %.2f by more than %.0f%%'
                        ) % (rec.consumption_rate, avg, threshold_pct)
                        continue

            # Anomali berbasis L/jam (untuk kapal/mesin)
            if rec.consumption_per_hour > 0 and rec.engine_hours > 0:
                expected_qty = rec.consumption_per_hour * rec.engine_hours
                if rec.qty_liters > expected_qty * (1 + threshold_pct / 100.0):
                    rec.is_anomaly = True
                    rec.anomaly_reason = _(
                        'Qty %.2f L exceeds expected %.2f L (%.0f%% over normal rate)'
                    ) % (rec.qty_liters, expected_qty, threshold_pct)

    def _get_vehicle_avg_consumption(self):
        """Hitung rata-rata consumption_rate untuk vehicle & fuel_type yang sama."""
        self.ensure_one()
        past = self.search([
            ('vehicle_id', '=', self.vehicle_id.id),
            ('fuel_type_id', '=', self.fuel_type_id.id),
            ('state', 'in', ('approved', 'posted')),
            ('consumption_rate', '>', 0),
            ('id', '!=', self._origin.id),
        ], limit=20)
        if not past:
            return 0.0
        return sum(past.mapped('consumption_rate')) / len(past)

    # ─── Onchange ────────────────────────────────────────────────────────────
    @api.onchange('fuel_type_id')
    def _onchange_fuel_type(self):
        if self.fuel_type_id and self.fuel_type_id.default_price:
            self.price_per_liter = self.fuel_type_id.default_price

    @api.onchange('transaction_type')
    def _onchange_transaction_type(self):
        if self.transaction_type == 'refuel':
            self.trip_id = False

    # ─── Constraints ─────────────────────────────────────────────────────────
    @api.constrains('odometer_start', 'odometer_end')
    def _check_odometer(self):
        for rec in self:
            if rec.odometer_start and rec.odometer_end:
                if rec.odometer_end < rec.odometer_start:
                    raise ValidationError(_(
                        'Odometer End (%s) cannot be less than Odometer Start (%s).'
                    ) % (rec.odometer_end, rec.odometer_start))

    @api.constrains('qty_liters')
    def _check_qty(self):
        for rec in self:
            if rec.qty_liters <= 0:
                raise ValidationError(_('Fuel quantity must be greater than zero.'))

    # ─── ORM ─────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.fuel.log') or _('New')
        return super().create(vals_list)

    # ─── State Actions ───────────────────────────────────────────────────────
    def action_submit(self):
        """Draft → To Approve."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only Draft fuel logs can be submitted.'))
            rec.state = 'to_approve'
            rec.message_post(body=_('Fuel log submitted for approval.'))
            # Notif anomali jika terdeteksi
            if rec.is_anomaly and not rec.anomaly_notified:
                rec._notify_anomaly()

    def action_approve(self):
        """To Approve → Approved: consume stock."""
        self._check_fleet_manager()
        for rec in self:
            if rec.state != 'to_approve':
                raise UserError(_('Only logs in "To Approve" state can be approved.'))
            rec._create_stock_move()
            rec.state = 'approved'
            rec.message_post(body=_('Fuel log approved. Stock move created.'))

    def action_post(self):
        """Approved → Posted: create journal entry."""
        self._check_fleet_manager()
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('Only Approved logs can be posted.'))
            rec._create_journal_entry()
            rec.state = 'posted'
            rec.message_post(body=_(
                'Fuel log posted. Journal entry: <b>%s</b>') % (
                rec.account_move_id.name if rec.account_move_id else '-'
            ))

    def action_cancel(self):
        """Cancel from draft/to_approve."""
        for rec in self:
            if rec.state in ('approved', 'posted'):
                raise UserError(_('Cannot cancel an Approved or Posted fuel log.'))
            rec.state = 'cancelled'
            rec.message_post(body=_('Fuel log cancelled.'))

    def action_reset_draft(self):
        """Cancelled → Draft."""
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_('Only cancelled logs can be reset to draft.'))
            rec.state = 'draft'

    def _check_fleet_manager(self):
        if not self.env.user.has_group('fleet_fuel_log.group_fleet_manager'):
            raise UserError(_('Only Fleet Managers can perform this action.'))

    # ─── Business Logic ──────────────────────────────────────────────────────
    def _create_stock_move(self):
        """Buat stock.move untuk konsumsi BBM dari Inventory."""
        self.ensure_one()
        if self.stock_move_id:
            return
        product = self.fuel_type_id.product_id
        if not product:
            _logger.warning('Fuel type %s has no product. Skipping stock move.', self.fuel_type_id.name)
            return

        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        src_location = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        dest_location = self.env.ref('stock.stock_location_production', raise_if_not_found=False)
        if not src_location or not dest_location:
            _logger.warning('Stock locations not found. Skipping stock move.')
            return

        uom = self.fuel_type_id.uom_id or product.uom_id
        move = self.env['stock.move'].create({
            'name': _('Fuel consumption: %s') % self.name,
            'product_id': product.id,
            'product_uom_qty': self.qty_liters,
            'product_uom': uom.id,
            'location_id': src_location.id,
            'location_dest_id': dest_location.id,
            'origin': self.name,
            'company_id': self.company_id.id,
        })
        move._action_confirm()
        move._action_assign()
        move._action_done()
        self.stock_move_id = move

    def _create_journal_entry(self):
        """Buat account.move (vendor bill / journal entry) untuk biaya BBM."""
        self.ensure_one()
        if self.account_move_id:
            return
        account = self.fuel_type_id.account_id
        if not account:
            _logger.warning('Fuel type %s has no expense account. Skipping journal entry.', self.fuel_type_id.name)
            return

        journal = self.env['account.journal'].search([
            ('type', 'in', ('purchase', 'general')),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not journal:
            _logger.warning('No suitable journal found. Skipping journal entry.')
            return

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': self.date,
            'ref': self.name,
            'company_id': self.company_id.id,
            'line_ids': [
                # Debit: beban BBM
                (0, 0, {
                    'name': _('%s — %s') % (self.fuel_type_id.name, self.vehicle_id.name),
                    'account_id': account.id,
                    'debit': self.total_cost,
                    'credit': 0.0,
                    'currency_id': self.currency_id.id,
                }),
                # Credit: akun sementara (clearing) — sesuaikan dengan CoA masing-masing
                (0, 0, {
                    'name': _('Fuel payable — %s') % self.name,
                    'account_id': self._get_clearing_account().id,
                    'debit': 0.0,
                    'credit': self.total_cost,
                    'currency_id': self.currency_id.id,
                }),
            ],
        })
        move.action_post()
        self.account_move_id = move

    def _get_clearing_account(self):
        """Cari akun kredit (utang/clearing). Fallback ke account payable perusahaan."""
        account = self.env['account.account'].search([
            ('account_type', '=', 'liability_payable'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not account:
            raise UserError(_('No payable account found. Please configure the Chart of Accounts.'))
        return account

    def _notify_anomaly(self):
        """Kirim email notifikasi ke Fleet Manager bila ada anomali konsumsi."""
        self.ensure_one()
        template = self.env.ref(
            'fleet_fuel_log.email_template_fuel_anomaly',
            raise_if_not_found=False,
        )
        manager = self.fleet_manager_id or self.env.ref('base.user_admin', raise_if_not_found=False)
        if template and manager:
            try:
                template.with_context(manager_email=manager.email).send_mail(
                    self.id, force_send=True
                )
                self.anomaly_notified = True
                self.message_post(body=_(
                    'Anomaly notification sent to Fleet Manager (%s).') % manager.name
                )
            except Exception as e:
                _logger.error('Failed to send anomaly notification: %s', str(e))

    # ─── Cron ────────────────────────────────────────────────────────────────
    @api.model
    def _cron_check_anomalies(self):
        """Cron harian — cek anomali pada log yang baru disubmit dan belum dinotifikasi."""
        logs = self.search([
            ('state', 'in', ('to_approve', 'approved')),
            ('is_anomaly', '=', True),
            ('anomaly_notified', '=', False),
        ])
        for log in logs:
            log._notify_anomaly()

    # ─── Smart Buttons ───────────────────────────────────────────────────────
    def action_view_stock_move(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.move',
            'view_mode': 'form',
            'res_id': self.stock_move_id.id,
            'target': 'current',
        }

    def action_view_journal_entry(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.account_move_id.id,
            'target': 'current',
        }
