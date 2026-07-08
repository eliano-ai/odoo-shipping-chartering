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
    # mail.activity.mixin ditambah Sprint 20 (awalnya cuma mail.thread sesuai §3.2 tech
    # spec) — _cron_pnl_pending_lock_alert butuh activity_schedule. Pre-flight check
    # sebelum pakai, bukan nunggu error dulu (pelajaran retro Sprint 8-14).
    _inherit = ['mail.thread', 'mail.activity.mixin']
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

    # ── Variance vs Estimate (§2.4) ─────────────────────────────────────
    # store=True wajib untuk compute field yang dipakai sebagai measure pivot (Odoo
    # 19 pivot "Measures" dropdown bisa pilih field apapun, bukan cuma yang sudah
    # dideklarasi di XML) -- aggregator= attribute SENDIRIAN TIDAK CUKUP untuk field
    # non-stored, Odoo tetap coba validasi lewat SQL SELECT beneran & gagal diam-diam
    # (lihat catatan lebih lengkap di vessel_vessel_budget_line.py). Di sini AMAN
    # di-store (beda dari budget_line) karena @api.depends di bawah cover semua
    # sumber data sungguhan (semua field lokal/related di model yang sama, bukan
    # search() lintas-model) -- tidak ada risiko stale. Ditemukan dari laporan error
    # user 2026-07-08.
    revenue_variance = fields.Monetary(
        string='Variance Revenue', compute='_compute_estimate_variance', store=True,
    )
    revenue_variance_pct = fields.Float(
        string='Variance Revenue (%)', compute='_compute_estimate_variance', store=True,
    )
    cost_variance = fields.Monetary(
        string='Variance Cost', compute='_compute_estimate_variance', store=True,
    )
    cost_variance_pct = fields.Float(
        string='Variance Cost (%)', compute='_compute_estimate_variance', store=True,
    )
    tce_variance = fields.Monetary(
        string='Variance TCE', compute='_compute_estimate_variance', store=True,
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

    @api.depends('voyage_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('%(voyage)s — Voyage P&L') % {
                'voyage': rec.voyage_id.name or _('Voyage'),
            }

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

    @api.depends('estimate_id', 'total_revenue', 'total_direct_cost',
                 'total_allocated_cost', 'tce_actual_per_day')
    def _compute_estimate_variance(self):
        """§2.4 — variance per komponen (bukan cuma total) supaya jadi feedback loop
        akurasi estimasi ke Chartering Manager. store=True (2026-07-08, awalnya
        non-stored) supaya bisa dipakai sebagai measure pivot — lihat catatan
        lengkap di field definition di atas."""
        for rec in self:
            estimate = rec.estimate_id
            if not estimate:
                rec.revenue_variance = 0.0
                rec.revenue_variance_pct = 0.0
                rec.cost_variance = 0.0
                rec.cost_variance_pct = 0.0
                rec.tce_variance = 0.0
                continue
            rec.revenue_variance = rec.total_revenue - estimate.revenue_estimate
            rec.revenue_variance_pct = (
                (rec.revenue_variance / estimate.revenue_estimate) * 100.0
                if estimate.revenue_estimate else 0.0
            )
            actual_total_cost = rec.total_direct_cost + rec.total_allocated_cost
            rec.cost_variance = actual_total_cost - estimate.total_cost_estimate
            rec.cost_variance_pct = (
                (rec.cost_variance / estimate.total_cost_estimate) * 100.0
                if estimate.total_cost_estimate else 0.0
            )
            rec.tce_variance = rec.tce_actual_per_day - estimate.tce_per_day

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
            rec._send_pnl_ready_email()
            rec._send_estimate_variance_email_if_significant()

    def _send_pnl_ready_email(self):
        """§4.6 — email siap-review ke Finance, trigger saat state jadi computed."""
        self.ensure_one()
        template = self.env.ref(
            'vessel_voyage_pnl.email_template_pnl_ready_for_review', raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.id, force_send=False)

    def _send_estimate_variance_email_if_significant(self):
        """§4.6 — variance estimate >25% (revenue atau cost) -> email ke Chartering
        Manager, feedback akurasi fixture."""
        self.ensure_one()
        if not self.estimate_id:
            return
        if abs(self.revenue_variance_pct) > 25.0 or abs(self.cost_variance_pct) > 25.0:
            template = self.env.ref(
                'vessel_voyage_pnl.email_template_pnl_estimate_variance_significant',
                raise_if_not_found=False,
            )
            if template:
                template.send_mail(self.id, force_send=False)

    @api.model
    def _cron_pnl_pending_lock_alert(self):
        """§4.5 — mingguan, voyage P&L state=computed > 14 hari belum di-lock ->
        activity ke Finance."""
        deadline = fields.Datetime.now() - timedelta(days=14)
        pending = self.search([
            ('state', '=', 'computed'),
            ('computed_date', '<=', deadline),
        ])
        finance_group = self.env.ref('account.group_account_invoice', raise_if_not_found=False)
        recipients = finance_group.user_ids if finance_group else self.env['res.users']
        for pnl in pending:
            existing_users = self.env['mail.activity'].search([
                ('res_model', '=', 'vessel.voyage.pnl'),
                ('res_id', '=', pnl.id),
            ]).mapped('user_id')
            for user in (recipients - existing_users):
                # Guard idempotency: -u ulang / cron re-trigger tidak boleh dobel
                # activity untuk record + user yang sama.
                pnl.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_('Voyage P&L Belum Di-lock >14 Hari'),
                    note=_(
                        'Voyage %(voyage)s sudah computed sejak %(date)s, belum di-lock.'
                    ) % {'voyage': pnl.voyage_id.name, 'date': pnl.computed_date},
                    user_id=user.id,
                )

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

    def action_view_voyage(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'vessel.voyage',
            'res_id': self.voyage_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_contract(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'vessel.charter.contract',
            'res_id': self.contract_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_estimate(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'vessel.voyage.estimate',
            'res_id': self.estimate_id.id,
            'view_mode': 'form',
            'target': 'current',
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

    def _convert_to_pnl_currency(self, amount, from_currency, date):
        """§2.4 tech spec — 'line lintas-mata-uang dikonversi kurs tanggal transaksi
        masing-masing'. self.currency_id = company currency (bukan otomatis USD di
        environment ini, lihat CLAUDE.md), sementara sumber baris revenue (invoice
        freight/demurrage) & sebagian port disbursement genuinely dalam USD (kontrak
        charter sengaja pakai currency USD, §2.4 vessel_chartering) — no-op kalau
        currency sumber & tujuan sudah sama."""
        self.ensure_one()
        if not amount or not from_currency or from_currency == self.currency_id:
            return amount
        return from_currency._convert(
            amount, self.currency_id, self.company_id,
            date or fields.Date.context_today(self),
        )

    def _compute_revenue(self):
        """§2.2 — Freight, Demurrage, Despatch dari account.move.line (analytic voyage),
        Brokerage dihitung langsung dari kontrak (bukan dari move, karena brokerage
        tidak pernah diinvoice sebagai baris terpisah di vessel_chartering). Semua
        dikonversi ke self.currency_id (§2.4 — lihat _convert_to_pnl_currency)."""
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
                    amount = self._convert_to_pnl_currency(aml.price_subtotal, aml.currency_id, aml.date)
                    freight_total += amount
                    self._create_line(
                        'cost_category_freight_revenue', amount,
                        aml.name or _('Freight'), 'account.move.line', aml.id,
                    )

            demurrage_product = self.env.ref(
                'vessel_chartering.product_demurrage', raise_if_not_found=False,
            )
            if demurrage_product:
                for aml in self._search_analytic_move_lines(demurrage_product.id, analytic_id):
                    amount = self._convert_to_pnl_currency(aml.price_subtotal, aml.currency_id, aml.date)
                    if aml.move_id.move_type == 'out_invoice':
                        signed = amount
                    elif aml.move_id.move_type == 'out_refund':
                        signed = -amount
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
            brokerage_usd = contract.freight_amount_final * (contract.brokerage_pct / 100.0)
            brokerage_date = self.voyage_id.date_departure or fields.Date.context_today(self)
            brokerage_total = self._convert_to_pnl_currency(
                brokerage_usd, contract.currency_id, brokerage_date,
            )
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
        vessel.pnl.cost.category.default_account_ids. Semua dikonversi ke
        self.currency_id (§2.4) — bunker/fleet_maintenance_schedule biasanya sudah
        company currency (no-op), tapi port disbursement genuinely bisa USD atau IDR
        per record ("sesuai kebiasaan agen", §3 tech spec vessel_voyage_operations)."""
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
                amount = self._convert_to_pnl_currency(log.total_cost, log.currency_id, log.date)
                bunker_total += amount
                self._create_line(
                    'cost_category_bunker', -amount,
                    log.display_name or _('Fuel Log'), 'fleet.fuel.log', log.id,
                )

        port_total = 0.0
        fdas = self.env['vessel.port.disbursement'].search([
            ('port_call_id.voyage_id', '=', voyage.id),
            ('disbursement_type', '=', 'fda'),
            ('state', '=', 'confirmed'),
        ])
        port_cost_date = voyage.date_departure or fields.Date.context_today(self)
        for fda in fdas:
            amount = self._convert_to_pnl_currency(fda.total_amount, fda.currency_id, port_cost_date)
            port_total += amount
            self._create_line(
                'cost_category_port_cost', -amount,
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
        ada), Overhead pakai fixed_percentage (tidak butuh pool).

        NB: dipanggil baik dari record singleton (_compute_allocation_for_category)
        MAUPUN dari recordset kosong `self.env['vessel.voyage.pnl']`
        (vessel_vessel_pnl._compute_totals) — jangan pakai `self.currency_id`/
        `self._convert_to_pnl_currency` di sini (butuh self.ensure_one()), konversi
        langsung ke company currency lewat self.env.company."""
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
            company = self.env.company
            company_currency = company.currency_id
            total = 0.0
            for s in schedules:
                amount = s.actual_cost
                if s.currency_id and s.currency_id != company_currency:
                    amount = s.currency_id._convert(
                        amount, company_currency, company,
                        s.completed_date or fields.Date.context_today(self),
                    )
                total += amount
            return total
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
            amount = abs(self._convert_to_pnl_currency(aml.price_subtotal, aml.currency_id, aml.date))
            total += amount
            self._create_line(
                cost_category_xmlid, -amount,
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
                    # price_per_liter 1.2 (IDR) tidak realistis (bunker Rp 1,2/liter,
                    # sisa dari sebelum currency conversion fix) -- Rp 12.000/liter
                    # mendekati harga riil HSD/MFO non-subsidi, supaya voyage_result
                    # jadi kerugian genuine setelah §2.4 currency conversion, bukan cuma
                    # "untung besar" karena cost tidak pernah diskalakan ulang (QA fix
                    # 2026-07-08 -- lihat juga vessel_bunker_rob_reconciliation.py).
                    'price_per_liter': 12000,
                    'state': 'approved',
                })

        # Pool Maintenance — replikasi angka acceptance criteria §10.4 (pool 30,000).
        # Ratio real yang keluar bukan persis 10/30 (tergantung total hari voyage kapal
        # ini bulan itu, termasuk voyage kedua dari _demo_setup_second_voyage_same_month
        # Sprint 18) — pembuktian formula 10/30 -> 10,000 persis dilakukan via unit test
        # (angka murni, tidak tergantung fixture demo), lihat tests/test_allocation.py.
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

    @api.model
    def _demo_setup_second_voyage_same_month(self):
        """§10.7 acceptance criteria — 2 voyage kapal yang sama overlap bulan yang sama,
        supaya agregasi vessel.vessel.pnl (utilization_pct, avg_tce) bisa diverifikasi
        dengan data nyata. Idempoten — guard cek existing sebelum create."""
        voyage3 = self.env.ref('vessel_voyage_operations.demo_voyage_3', raise_if_not_found=False)
        contract3 = self.env.ref(
            'vessel_chartering.demo_contract_coa_shipment_3', raise_if_not_found=False,
        )
        if not voyage3 or not contract3 or not voyage3.date_arrival_final:
            return

        voyage2 = self.env['vessel.voyage'].search([
            ('charter_contract_id', '=', contract3.id),
        ], limit=1)
        if not voyage2:
            contract3._ensure_voyage_analytic_account()
            departure = voyage3.date_arrival_final + timedelta(days=3)
            arrival = departure + timedelta(days=4)
            voyage2 = self.env['vessel.voyage'].create({
                'charter_contract_id': contract3.id,
                'origin_port_id': voyage3.origin_port_id.id,
                'final_port_id': voyage3.final_port_id.id,
                'date_departure': departure,
                'date_arrival_final': arrival,
                'state': 'completed',
            })

        freight_product = self.env.ref('vessel_chartering.product_freight_revenue')
        existing_freight = self.env['account.move'].search([
            ('charter_contract_id', '=', contract3.id),
            ('invoice_line_ids.product_id', '=', freight_product.id),
        ], limit=1)
        if not existing_freight:
            move = contract3._create_freight_invoice(100)
            move.action_post()

        existing_pnl2 = self.env['vessel.voyage.pnl'].search([('voyage_id', '=', voyage2.id)], limit=1)
        if not existing_pnl2:
            pnl2 = self.create({'voyage_id': voyage2.id})
            pnl2.action_generate_pnl()
        else:
            existing_pnl2.action_recompute()

        # Voyage pertama (demo_voyage_3) perlu di-recompute ulang supaya alokasi
        # per_voyage_day-nya ikut memperhitungkan total hari operasi kapal yang sudah
        # bertambah (kedua voyage bulan yang sama), bukan cuma dirinya sendiri.
        pnl1 = self.env['vessel.voyage.pnl'].search([('voyage_id', '=', voyage3.id)])
        if pnl1 and pnl1.state != 'locked':
            pnl1.action_recompute()

        vessel = voyage3.vessel_id
        year, month = voyage3.date_departure.year, voyage3.date_departure.month
        vessel_pnl = self.env['vessel.vessel.pnl'].search([
            ('vessel_id', '=', vessel.id),
            ('period_month', '=', str(month)),
            ('period_year', '=', year),
        ], limit=1)
        if not vessel_pnl:
            self.env['vessel.vessel.pnl'].create({
                'vessel_id': vessel.id,
                'period_month': str(month),
                'period_year': year,
            })

    @api.model
    def _demo_setup_orphan_voyage_for_backfill(self):
        """Sprint 20 — sengaja SATU voyage completed dengan freight invoice posted
        TAPI belum di-generate P&L-nya, supaya wizard Generate P&L Massal ada sesuatu
        nyata untuk diverifikasi (bukan 0 hasil). Idempoten — guard existing sebelum
        create, dan TIDAK memanggil action_generate_pnl (biar tetap orphan sampai
        wizard/verifikasi manual yang generate)."""
        contract2 = self.env.ref(
            'vessel_chartering.demo_contract_coa_shipment_2', raise_if_not_found=False,
        )
        if not contract2:
            return
        voyage = self.env['vessel.voyage'].search([
            ('charter_contract_id', '=', contract2.id),
        ], limit=1)
        if not voyage:
            contract2._ensure_voyage_analytic_account()
            departure = fields.Datetime.now() - timedelta(days=15)
            arrival = fields.Datetime.now() - timedelta(days=10)
            voyage = self.env['vessel.voyage'].create({
                'charter_contract_id': contract2.id,
                'date_departure': departure,
                'date_arrival_final': arrival,
                'state': 'completed',
            })
            freight_product = self.env.ref('vessel_chartering.product_freight_revenue')
            existing_freight = self.env['account.move'].search([
                ('charter_contract_id', '=', contract2.id),
                ('invoice_line_ids.product_id', '=', freight_product.id),
            ], limit=1)
            if not existing_freight:
                move = contract2._create_freight_invoice(100)
                move.action_post()
