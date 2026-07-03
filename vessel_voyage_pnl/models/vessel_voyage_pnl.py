# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

STATE = [
    ('draft', 'Draft'),
    ('computed', 'Computed'),
    ('locked', 'Locked'),
]


class VesselVoyagePnl(models.Model):
    _name = 'vessel.voyage.pnl'
    _description = 'P&L per Voyage'
    _inherit = ['mail.thread']
    _order = 'voyage_id desc'

    voyage_id = fields.Many2one(
        'vessel.voyage', string='Voyage', required=True,
        domain=[('state', '=', 'completed')], tracking=True,
    )
    contract_id = fields.Many2one(
        'vessel.charter.contract', string='Kontrak Charter',
        related='voyage_id.charter_contract_id', store=True, readonly=True,
    )
    vessel_id = fields.Many2one(
        'fleet.vehicle', string='Kapal',
        related='voyage_id.vessel_id', store=True, readonly=True,
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account (Voyage)',
        related='voyage_id.analytic_account_id', store=True, readonly=True,
    )
    estimate_id = fields.Many2one(
        'vessel.voyage.estimate', string='Estimate Baseline',
        help='Auto-set ke estimate ber-state selected milik kontrak, editable override.',
    )
    voyage_days = fields.Float(
        string='Voyage Days', compute='_compute_voyage_days', store=True,
    )

    # ── Revenue ──────────────────────────────────────────────────────────
    # NB: field-field revenue/direct-cost DI BAWAH ini SENGAJA bukan
    # @api.depends compute biasa (walau di tech spec ditulis "compute, store")
    # — kalau live-recompute tiap kali dependency berubah, snapshot yang
    # sudah di-lock bisa berubah diam-diam saat data sumber dikoreksi
    # belakangan (lihat §8 tech spec: P&L harus jadi titik waktu yang tidak
    # berubah setelah locked). Field ini diisi imperatif oleh
    # _compute_revenue()/_compute_direct_cost(), dipanggil tombol
    # Generate/Recompute — bukan otomatis oleh ORM.
    freight_revenue = fields.Monetary(string='Freight Revenue', readonly=True)
    demurrage_revenue = fields.Monetary(string='Demurrage Revenue', readonly=True)
    despatch_cost = fields.Monetary(string='Despatch (Cost)', readonly=True)
    brokerage_cost = fields.Monetary(string='Brokerage', readonly=True)
    other_revenue = fields.Monetary(string='Other Revenue')
    total_revenue = fields.Monetary(
        string='Total Revenue', compute='_compute_total_revenue', store=True,
    )

    # ── Direct Cost ──────────────────────────────────────────────────────
    bunker_cost = fields.Monetary(string='Bunker Cost', readonly=True)
    port_cost = fields.Monetary(string='Port Cost', readonly=True)
    cargo_handling_cost = fields.Monetary(string='Cargo Handling Cost', readonly=True)
    insurance_voyage_cost = fields.Monetary(string='Insurance Voyage', readonly=True)
    other_direct_cost = fields.Monetary(string='Other Direct Cost')
    total_direct_cost = fields.Monetary(
        string='Total Direct Cost', compute='_compute_total_direct_cost', store=True,
    )

    # ── Allocated Cost ───────────────────────────────────────────────────
    crew_cost_allocated = fields.Monetary(string='Crew Cost (Alokasi)', readonly=True)
    maintenance_cost_allocated = fields.Monetary(string='Maintenance (Alokasi)', readonly=True)
    depreciation_allocated = fields.Monetary(string='Depreciation (Alokasi)', readonly=True)
    overhead_allocated = fields.Monetary(string='Overhead (Alokasi)', readonly=True)
    total_allocated_cost = fields.Monetary(
        string='Total Allocated Cost', compute='_compute_total_allocated_cost', store=True,
    )

    # ── Hasil ────────────────────────────────────────────────────────────
    voyage_result = fields.Monetary(
        string='Voyage Result', compute='_compute_voyage_result', store=True,
    )
    tce_actual_per_day = fields.Monetary(
        string='TCE Aktual / Hari', compute='_compute_voyage_result', store=True,
        help='(Total Revenue - Total Direct Cost) / Voyage Days — EXCLUDE allocated cost '
             '(crew/maintenance/depresiasi/overhead), konsisten definisi TCE standar industri.',
    )

    line_ids = fields.One2many('vessel.voyage.pnl.line', 'pnl_id', string='Rincian')
    state = fields.Selection(STATE, default='draft', required=True, tracking=True, copy=False)
    computed_date = fields.Datetime(string='Terakhir Dihitung', readonly=True, copy=False)
    locked_by = fields.Many2one('res.users', string='Dikunci Oleh', readonly=True, copy=False)
    locked_date = fields.Datetime(string='Tanggal Lock', readonly=True, copy=False)
    currency_id = fields.Many2one(
        'res.currency', string='Mata Uang',
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        'res.company', string='Perusahaan', required=True,
        default=lambda self: self.env.company,
    )

    _unique_voyage = models.Constraint('UNIQUE(voyage_id)', 'Voyage ini sudah punya P&L.')

    @api.depends('voyage_id.date_departure', 'voyage_id.date_arrival_final')
    def _compute_voyage_days(self):
        for rec in self:
            voyage = rec.voyage_id
            if voyage.date_departure and voyage.date_arrival_final:
                delta = voyage.date_arrival_final - voyage.date_departure
                rec.voyage_days = delta.total_seconds() / 86400.0
            else:
                rec.voyage_days = 0.0

    @api.depends('freight_revenue', 'demurrage_revenue', 'despatch_cost',
                 'brokerage_cost', 'other_revenue',
                 'line_ids.amount', 'line_ids.is_manual_adjustment', 'line_ids.category_group')
    def _compute_total_revenue(self):
        for rec in self:
            adjustment = sum(rec.line_ids.filtered(
                lambda l: l.is_manual_adjustment and l.category_group == 'revenue'
            ).mapped('amount'))
            rec.total_revenue = (
                rec.freight_revenue + rec.demurrage_revenue - rec.despatch_cost
                - rec.brokerage_cost + rec.other_revenue + adjustment
            )

    @api.depends('bunker_cost', 'port_cost', 'cargo_handling_cost',
                 'insurance_voyage_cost', 'other_direct_cost',
                 'line_ids.amount', 'line_ids.is_manual_adjustment', 'line_ids.category_group')
    def _compute_total_direct_cost(self):
        for rec in self:
            # Line adjustment cost tersimpan negatif (konvensi tanda line_ids.amount) —
            # negasikan supaya menambah total_direct_cost sebagai magnitude positif.
            adjustment = -sum(rec.line_ids.filtered(
                lambda l: l.is_manual_adjustment and l.category_group == 'direct_cost'
            ).mapped('amount'))
            rec.total_direct_cost = (
                rec.bunker_cost + rec.port_cost + rec.cargo_handling_cost
                + rec.insurance_voyage_cost + rec.other_direct_cost + adjustment
            )

    @api.depends('crew_cost_allocated', 'maintenance_cost_allocated',
                 'depreciation_allocated', 'overhead_allocated',
                 'line_ids.amount', 'line_ids.is_manual_adjustment', 'line_ids.category_group')
    def _compute_total_allocated_cost(self):
        for rec in self:
            adjustment = -sum(rec.line_ids.filtered(
                lambda l: l.is_manual_adjustment and l.category_group == 'allocated_cost'
            ).mapped('amount'))
            rec.total_allocated_cost = (
                rec.crew_cost_allocated + rec.maintenance_cost_allocated
                + rec.depreciation_allocated + rec.overhead_allocated + adjustment
            )

    @api.depends('total_revenue', 'total_direct_cost', 'total_allocated_cost', 'voyage_days')
    def _compute_voyage_result(self):
        for rec in self:
            rec.voyage_result = rec.total_revenue - rec.total_direct_cost - rec.total_allocated_cost
            if rec.voyage_days:
                rec.tce_actual_per_day = (rec.total_revenue - rec.total_direct_cost) / rec.voyage_days
            else:
                rec.tce_actual_per_day = 0.0

    # ── Generate / Recompute ────────────────────────────────────────────
    def action_generate_pnl(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Hanya P&L Draft yang bisa di-generate.'))
            if not rec.estimate_id:
                rec.estimate_id = rec.contract_id.estimate_ids.filtered(
                    lambda e: e.state == 'selected'
                )[:1]
            rec._compute_revenue()
            rec._compute_direct_cost()
            rec._compute_allocated_cost()
            rec.state = 'computed'
            rec.computed_date = fields.Datetime.now()

    def action_recompute(self):
        for rec in self:
            if rec.state not in ('draft', 'computed'):
                raise UserError(_('Recompute hanya bisa dilakukan saat state Draft/Computed.'))
            rec._compute_revenue()
            rec._compute_direct_cost()
            rec._compute_allocated_cost()
            rec.computed_date = fields.Datetime.now()

    def action_lock(self):
        for rec in self:
            if rec.state != 'computed':
                raise UserError(_('Hanya P&L Computed yang bisa di-Lock.'))
            if not (self.env.user.has_group('vessel_voyage_pnl.group_voyage_pnl_finance')
                    or self.env.user.has_group('vessel_voyage_pnl.group_voyage_pnl_manager')):
                raise UserError(_('Hanya Finance/Manager yang bisa melakukan Lock.'))
            rec.state = 'locked'
            rec.locked_by = self.env.user.id
            rec.locked_date = fields.Datetime.now()

    def action_open_adjustment_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Adjustment Manual — %s') % self.display_name,
            'res_model': 'vessel.pnl.adjustment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_pnl_id': self.id},
        }

    def _clear_auto_lines(self, category_group):
        """Hapus line non-manual (bukan adjustment Finance) untuk grup kategori tertentu,
        supaya Recompute tidak menumpuk duplikat."""
        self.line_ids.filtered(
            lambda l: not l.is_manual_adjustment and l.category_group == category_group
        ).unlink()

    def _create_line(self, cost_category_xmlid, amount, description,
                      source_model=False, source_res_id=False,
                      is_allocated=False, allocation_rule_id=False):
        category = self.env.ref('vessel_voyage_pnl.%s' % cost_category_xmlid)
        return self.env['vessel.voyage.pnl.line'].create({
            'pnl_id': self.id,
            'cost_category_id': category.id,
            'amount': amount,
            'description': description,
            'source_model': source_model,
            'source_res_id': source_res_id,
            'is_allocated': is_allocated,
            'allocation_rule_id': allocation_rule_id,
        })

    def _compute_revenue(self):
        """§2.2 — Freight, Demurrage, Despatch dari account.move.line (analytic voyage),
        Brokerage dihitung langsung dari kontrak (bukan dari move, karena brokerage
        tidak pernah diinvoice sebagai baris terpisah di vessel_chartering)."""
        self.ensure_one()
        self._clear_auto_lines('revenue')
        contract = self.contract_id
        analytic_id = self.analytic_account_id.id

        freight_total = 0.0
        demurrage_total = 0.0
        despatch_total = 0.0

        if analytic_id:
            freight_product = self.env.ref(
                'vessel_chartering.product_freight_revenue', raise_if_not_found=False,
            )
            if freight_product:
                for aml in self._search_analytic_move_lines(freight_product.id, analytic_id):
                    if aml.move_id.move_type != 'out_invoice':
                        continue
                    freight_total += aml.price_subtotal
                    self._create_line(
                        'cost_category_freight_revenue', aml.price_subtotal,
                        aml.name or _('Freight'), 'account.move.line', aml.id,
                    )

            demurrage_product = self.env.ref(
                'vessel_chartering.product_demurrage', raise_if_not_found=False,
            )
            if demurrage_product:
                for aml in self._search_analytic_move_lines(demurrage_product.id, analytic_id):
                    if aml.move_id.move_type == 'out_invoice':
                        signed = aml.price_subtotal
                    elif aml.move_id.move_type == 'out_refund':
                        signed = -aml.price_subtotal
                    else:
                        continue
                    if signed >= 0:
                        demurrage_total += signed
                        self._create_line(
                            'cost_category_demurrage', signed,
                            aml.name or _('Demurrage'), 'account.move.line', aml.id,
                        )
                    else:
                        despatch_total += -signed
                        self._create_line(
                            'cost_category_despatch', signed,
                            aml.name or _('Despatch'), 'account.move.line', aml.id,
                        )

        brokerage_total = 0.0
        if contract and contract.brokerage_pct:
            brokerage_total = contract.freight_amount_final * (contract.brokerage_pct / 100.0)
            if brokerage_total:
                self._create_line(
                    'cost_category_brokerage', -brokerage_total,
                    _('Brokerage %(pct)s%% dari freight') % {'pct': contract.brokerage_pct},
                    'vessel.charter.contract', contract.id,
                )

        self.write({
            'freight_revenue': freight_total,
            'demurrage_revenue': demurrage_total,
            'despatch_cost': despatch_total,
            'brokerage_cost': brokerage_total,
        })

    def _compute_direct_cost(self):
        """§2.2 — Bunker dari fleet_fuel_log (via bridge fleet_trip_id), Port Cost dari
        FDA confirmed, Cargo Handling/Insurance dari account.move.line ter-mapping
        vessel.pnl.cost.category.default_account_ids."""
        self.ensure_one()
        self._clear_auto_lines('direct_cost')
        voyage = self.voyage_id

        bunker_total = 0.0
        if voyage.fleet_trip_id:
            fuel_logs = self.env['fleet.fuel.log'].search([
                ('trip_id', '=', voyage.fleet_trip_id.id),
                ('state', 'in', ('approved', 'posted')),
            ])
            for log in fuel_logs:
                bunker_total += log.total_cost
                self._create_line(
                    'cost_category_bunker', -log.total_cost,
                    log.display_name or _('Fuel Log'), 'fleet.fuel.log', log.id,
                )

        port_total = 0.0
        fdas = self.env['vessel.port.disbursement'].search([
            ('port_call_id.voyage_id', '=', voyage.id),
            ('disbursement_type', '=', 'fda'),
            ('state', '=', 'confirmed'),
        ])
        for fda in fdas:
            port_total += fda.total_amount
            self._create_line(
                'cost_category_port_cost', -fda.total_amount,
                fda.display_name or _('Port Disbursement (FDA)'),
                'vessel.port.disbursement', fda.id,
            )

        cargo_handling_total = self._compute_mapped_account_cost(
            'cost_category_cargo_handling',
        )
        insurance_total = self._compute_mapped_account_cost(
            'cost_category_insurance_voyage',
        )

        self.write({
            'bunker_cost': bunker_total,
            'port_cost': port_total,
            'cargo_handling_cost': cargo_handling_total,
            'insurance_voyage_cost': insurance_total,
        })

    # ── Allocated Cost (§2.3, §4.2) ─────────────────────────────────────
    # Field -> xmlid kategori biaya allocated_cost yang di-seed Sprint 15.
    _ALLOCATED_FIELD_MAP = {
        'cost_category_crew_cost': 'crew_cost_allocated',
        'cost_category_maintenance': 'maintenance_cost_allocated',
        'cost_category_depreciation': 'depreciation_allocated',
        'cost_category_overhead': 'overhead_allocated',
    }

    def _compute_allocated_cost(self):
        """Baca vessel.cost.allocation.rule aktif per kategori, alokasikan pool bulanan
        kapal sesuai allocation_method (§2.3) — satu function terpisah per method supaya
        gampang ditambah metode baru fase 2 (§12.2 poin 4)."""
        self.ensure_one()
        self._clear_auto_lines('allocated_cost')
        rules_by_category = {
            r.cost_category_id.id: r
            for r in self.env['vessel.cost.allocation.rule'].search([('active', '=', True)])
        }
        values = {}
        for xmlid, field_name in self._ALLOCATED_FIELD_MAP.items():
            category = self.env.ref('vessel_voyage_pnl.%s' % xmlid, raise_if_not_found=False)
            if not category:
                values[field_name] = 0.0
                continue
            rule = rules_by_category.get(category.id)
            amount = self._compute_allocation_for_category(category, rule)
            values[field_name] = amount
            if amount:
                self._create_line(
                    xmlid, -amount,
                    _('Alokasi %(method)s') % {
                        'method': dict(rule._fields['allocation_method'].selection).get(
                            rule.allocation_method,
                        ) if rule else 'Manual',
                    },
                    is_allocated=True, allocation_rule_id=rule.id if rule else False,
                )
        self.write(values)

    def _compute_allocation_for_category(self, category, rule):
        """Dispatch ke _allocate_<method>() sesuai allocation_method rule aktif."""
        self.ensure_one()
        method = rule.allocation_method if rule else 'manual'
        if method == 'manual' or not self.voyage_id.date_departure:
            return self._allocate_manual()

        if method == 'fixed_percentage':
            pct = rule.fixed_percentage_value if rule else 0.0
            return self._allocate_fixed_percentage(pct, self.total_revenue)

        vessel = self.vessel_id
        first_day, next_first_day = self._get_month_bounds(self.voyage_id.date_departure)
        pool = self._get_monthly_pool(vessel, category, first_day, next_first_day)
        if not pool:
            return 0.0

        if method == 'per_voyage_day':
            total_active_days = self._get_total_active_voyage_days(
                vessel, first_day, next_first_day,
            )
            return self._allocate_per_voyage_day(pool, self.voyage_days, total_active_days)
        if method == 'per_calendar_day':
            calendar_days = (next_first_day - first_day).days
            return self._allocate_per_calendar_day(pool, self.voyage_days, calendar_days)
        if method == 'equal_split':
            active_count = self.search_count([
                ('vessel_id', '=', vessel.id),
                ('voyage_id.date_departure', '>=', first_day),
                ('voyage_id.date_departure', '<', next_first_day),
            ])
            return self._allocate_equal_split(pool, active_count)
        return 0.0

    @api.model
    def _allocate_per_voyage_day(self, pool, voyage_days, total_active_days):
        """§10.4 acceptance criteria: pool 30,000, voyage 10/30 hari -> allocated 10,000."""
        if not total_active_days:
            return 0.0
        return pool * (voyage_days / total_active_days)

    @api.model
    def _allocate_per_calendar_day(self, pool, voyage_days_in_month, calendar_days):
        """Fase 2 (§9 tech spec) — belum diimplementasi penuh (butuh pro-rata pool per
        hari aktual lintas-bulan). Return 0.0 aman: tidak ada seed rule yang pakai method
        ini di MVP, cuma stub supaya pilihan di UI tidak crash kalau dipilih Finance."""
        return 0.0

    @api.model
    def _allocate_equal_split(self, pool, active_voyage_count):
        if not active_voyage_count:
            return 0.0
        return pool / active_voyage_count

    @api.model
    def _allocate_fixed_percentage(self, fixed_percentage_value, total_revenue):
        return total_revenue * ((fixed_percentage_value or 0.0) / 100.0)

    @api.model
    def _allocate_manual(self):
        return 0.0

    def _get_month_bounds(self, dt):
        """(awal_bulan, awal_bulan_berikutnya) sebagai date — pool diambil dari bulan
        date_departure voyage saja (§4.2 MVP, voyage lintas-bulan pro-rata di fase 2)."""
        d = dt.date() if hasattr(dt, 'date') else dt
        first = d.replace(day=1)
        if first.month == 12:
            next_first = first.replace(year=first.year + 1, month=1)
        else:
            next_first = first.replace(month=first.month + 1)
        return first, next_first

    def _get_monthly_pool(self, vessel, category, first_day, next_first_day):
        """Sumber pool cuma tersedia untuk Maintenance (fleet_maintenance_schedule) di
        MVP — Crew Cost & Depreciation selalu manual (hr_payroll/account_asset tidak
        ada), Overhead pakai fixed_percentage (tidak butuh pool)."""
        maintenance_cat = self.env.ref(
            'vessel_voyage_pnl.cost_category_maintenance', raise_if_not_found=False,
        )
        if maintenance_cat and category.id == maintenance_cat.id:
            schedules = self.env['fleet.maintenance.schedule'].search([
                ('vehicle_id', '=', vessel.id),
                ('state', '=', 'done'),
                ('completed_date', '>=', first_day),
                ('completed_date', '<', next_first_day),
            ])
            return sum(schedules.mapped('actual_cost'))
        return 0.0

    def _get_total_active_voyage_days(self, vessel, first_day, next_first_day):
        """Total hari voyage (semua vessel.voyage.pnl kapal ini) yang date_departure
        jatuh di bulan yang sama — proxy 'hari kapal beroperasi' (bukan hari kalender,
        supaya idle days tidak ikut terhitung, beda dari per_calendar_day)."""
        pnls = self.search([
            ('vessel_id', '=', vessel.id),
            ('voyage_id.date_departure', '>=', first_day),
            ('voyage_id.date_departure', '<', next_first_day),
        ])
        return sum(pnls.mapped('voyage_days'))

    def _compute_mapped_account_cost(self, cost_category_xmlid):
        """Kategori tanpa sumber terstruktur (Cargo Handling, Insurance Voyage) —
        di-mapping manual via vessel.pnl.cost.category.default_account_ids (§2.2).
        Kosong secara default sampai Finance konfigurasi akun terkait."""
        self.ensure_one()
        category = self.env.ref('vessel_voyage_pnl.%s' % cost_category_xmlid, raise_if_not_found=False)
        if not category or not category.default_account_ids or not self.analytic_account_id:
            return 0.0
        total = 0.0
        for aml in self._search_analytic_move_lines(
            False, self.analytic_account_id.id, account_ids=category.default_account_ids.ids,
        ):
            total += abs(aml.price_subtotal)
            self._create_line(
                cost_category_xmlid, -abs(aml.price_subtotal),
                aml.name or category.name, 'account.move.line', aml.id,
            )
        return total

    def _search_analytic_move_lines(self, product_id, analytic_account_id, account_ids=None):
        """Query account.move.line posted dengan analytic_distribution mengandung
        analytic_account_id ini — pakai raw SQL karena analytic_distribution adalah
        kolom jsonb, operator '?' (key exists) postgres lebih andal daripada domain
        ORM untuk kasus ini."""
        query = """
            SELECT aml.id
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            WHERE am.state = 'posted'
              AND aml.analytic_distribution ? %(analytic_key)s
        """
        params = {'analytic_key': str(analytic_account_id)}
        if product_id:
            query += ' AND aml.product_id = %(product_id)s'
            params['product_id'] = product_id
        if account_ids:
            query += ' AND aml.account_id = ANY(%(account_ids)s)'
            params['account_ids'] = list(account_ids)
        self.env.cr.execute(query, params)
        ids = [row[0] for row in self.env.cr.fetchall()]
        return self.env['account.move.line'].browse(ids)

    # ── Demo Data Setup (dipanggil via <function> di data/vessel_voyage_pnl_demo.xml) ──
    @api.model
    def _demo_setup_voyage3_sources(self):
        """Idempoten — aman dipanggil ulang tiap -u (guard cek existing sebelum create
        di tiap langkah). Menyiapkan sumber data lengkap (freight invoice, demurrage,
        FDA, bunker) untuk demo_voyage_3 supaya §10.2/§10.3 acceptance criteria bisa
        diverifikasi dengan data nyata, bukan cuma model kosong."""
        contract = self.env.ref(
            'vessel_chartering.demo_contract_coa_shipment_1', raise_if_not_found=False,
        )
        voyage = self.env.ref(
            'vessel_voyage_operations.demo_voyage_3', raise_if_not_found=False,
        )
        if not contract or not voyage:
            return

        contract._ensure_voyage_analytic_account()
        if not contract.demurrage_rate:
            contract.demurrage_rate = 8000.0
        if not contract.brokerage_pct:
            contract.brokerage_pct = 2.5

        freight_product = self.env.ref('vessel_chartering.product_freight_revenue')
        existing_freight = self.env['account.move'].search([
            ('charter_contract_id', '=', contract.id),
            ('invoice_line_ids.product_id', '=', freight_product.id),
        ], limit=1)
        if not existing_freight:
            move = contract._create_freight_invoice(100)
            move.action_post()

        laytime = self.env['vessel.laytime.calculation'].search([
            ('contract_id', '=', contract.id), ('port_call_type', '=', 'load'),
        ], limit=1)
        if not laytime:
            start = fields.Datetime.now() - timedelta(days=25)
            laytime = self.env['vessel.laytime.calculation'].create({
                'contract_id': contract.id,
                'port_call_type': 'load',
                'port_id': self.env.ref('vessel_chartering.demo_port_balikpapan').id,
                'nor_tendered': start,
                'nor_accepted': start,
                'laytime_allowed_hours': 96,
                'laytime_completed': start + timedelta(hours=120),
                'state': 'approved',
            })
            self.env['vessel.sof.line'].create({
                'laytime_id': laytime.id,
                'datetime_start': start,
                'datetime_end': start + timedelta(hours=120),
                'activity': 'Loading (demo, sengaja over allowed 96h -> demurrage 8000)',
                'is_counting': True,
            })

        demurrage_product = self.env.ref('vessel_chartering.product_demurrage')
        existing_demurrage = self.env['account.move'].search([
            ('charter_contract_id', '=', contract.id),
            ('invoice_line_ids.product_id', '=', demurrage_product.id),
            ('move_type', '=', 'out_invoice'),
        ], limit=1)
        if not existing_demurrage and laytime.demurrage_amount:
            move = contract._create_demurrage_invoice(laytime)
            move.action_post()

        port_call = self.env['vessel.port.call'].search([('voyage_id', '=', voyage.id)], limit=1)
        if not port_call:
            port_call = self.env['vessel.port.call'].create({
                'voyage_id': voyage.id,
                'port_id': self.env.ref('vessel_chartering.demo_port_tarahan').id,
                'call_purpose': 'discharge',
            })
        fda = self.env['vessel.port.disbursement'].search([
            ('port_call_id', '=', port_call.id), ('disbursement_type', '=', 'fda'),
        ], limit=1)
        if not fda:
            fda = self.env['vessel.port.disbursement'].create({
                'port_call_id': port_call.id,
                'disbursement_type': 'fda',
                'state': 'confirmed',
            })
            self.env['vessel.port.disbursement.line'].create({
                'disbursement_id': fda.id,
                'item_type_id': self.env.ref(
                    'vessel_voyage_operations.disbursement_item_port_dues',
                ).id,
                'amount': 12000,
            })

        if not voyage.fleet_trip_id:
            trip = self.env['fleet.vehicle.trip'].create({
                'name': _('Demo Trip — %s') % voyage.name,
                'vehicle_id': voyage.vessel_id.id,
                'departure_date': voyage.date_departure or fields.Datetime.now(),
                'arrival_date': voyage.date_arrival_final or fields.Datetime.now(),
                'state': 'done',
            })
            voyage.fleet_trip_id = trip.id
        if voyage.fleet_trip_id and not voyage.fleet_trip_id.fuel_log_ids:
            fuel_type = self.env['fleet.fuel.type'].search([], limit=1)
            if fuel_type:
                self.env['fleet.fuel.log'].create({
                    'vehicle_id': voyage.vessel_id.id,
                    'trip_id': voyage.fleet_trip_id.id,
                    'fuel_type_id': fuel_type.id,
                    'transaction_type': 'trip',
                    'qty_liters': 5000,
                    'price_per_liter': 1.2,
                    'state': 'approved',
                })

        # Pool Maintenance — replikasi angka acceptance criteria §10.4 (pool 30,000).
        # Ratio real yang keluar bukan persis 10/30 (voyage_days demo_voyage_3 = 5 hari,
        # satu-satunya voyage kapal ini bulan itu -> ratio 100%) — pembuktian formula
        # 10/30 -> 10,000 persis dilakukan via unit test (angka murni, tidak tergantung
        # fixture demo), lihat tests/test_allocation.py.
        existing_maintenance = self.env['fleet.maintenance.schedule'].search([
            ('vehicle_id', '=', voyage.vessel_id.id),
            ('maintenance_type', '=', 'preventive'),
            ('description', '=', 'Demo — Maintenance Voyage P&L (pool 30,000)'),
        ], limit=1)
        if not existing_maintenance:
            completed = (voyage.date_departure or fields.Datetime.now()).date()
            schedule = self.env['fleet.maintenance.schedule'].create({
                'vehicle_id': voyage.vessel_id.id,
                'maintenance_type': 'preventive',
                'description': 'Demo — Maintenance Voyage P&L (pool 30,000)',
                'schedule_basis': 'date',
                'scheduled_date': completed,
                'completed_date': completed,
                'state': 'done',
            })
            # unit_cost/subtotal_cost adalah compute+store yang saling bergantung
            # (unit_cost <- product_id.standard_price, subtotal_cost <- qty*unit_cost).
            # standard_price sendiri company-dependent (property field) — assignment
            # literal di create() tidak reliably persisten. Cara paling aman: create
            # dulu (apapun hasil compute-nya), baru overwrite subtotal_cost via write()
            # TERPISAH setelah create selesai — write() ke field biasa (bukan lewat
            # cascade compute dependency) tidak akan tertimpa ulang oleh compute lain.
            spare_part_product = self.env['product.product'].search([
                ('name', '=', 'Demo Sparepart — Voyage P&L Pool'),
            ], limit=1)
            if not spare_part_product:
                spare_part_product = self.env['product.product'].create({
                    'name': 'Demo Sparepart — Voyage P&L Pool',
                    'type': 'consu',
                })
            part = self.env['fleet.maintenance.part'].create({
                'schedule_id': schedule.id,
                'product_id': spare_part_product.id,
                'qty_planned': 1,
            })
            part.write({'subtotal_cost': 30000})

        existing_pnl = self.env['vessel.voyage.pnl'].search([('voyage_id', '=', voyage.id)], limit=1)
        if not existing_pnl:
            pnl = self.create({'voyage_id': voyage.id})
            pnl.action_generate_pnl()
        else:
            existing_pnl.action_recompute()
