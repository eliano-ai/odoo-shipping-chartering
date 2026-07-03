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

    line_ids = fields.One2many('vessel.voyage.pnl.line', 'pnl_id', string='Rincian')
    state = fields.Selection(STATE, default='draft', required=True, tracking=True, copy=False)
    computed_date = fields.Datetime(string='Terakhir Dihitung', readonly=True, copy=False)
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
                 'brokerage_cost', 'other_revenue')
    def _compute_total_revenue(self):
        for rec in self:
            rec.total_revenue = (
                rec.freight_revenue + rec.demurrage_revenue - rec.despatch_cost
                - rec.brokerage_cost + rec.other_revenue
            )

    @api.depends('bunker_cost', 'port_cost', 'cargo_handling_cost',
                 'insurance_voyage_cost', 'other_direct_cost')
    def _compute_total_direct_cost(self):
        for rec in self:
            rec.total_direct_cost = (
                rec.bunker_cost + rec.port_cost + rec.cargo_handling_cost
                + rec.insurance_voyage_cost + rec.other_direct_cost
            )

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
            rec.state = 'computed'
            rec.computed_date = fields.Datetime.now()

    def action_recompute(self):
        for rec in self:
            if rec.state not in ('draft', 'computed'):
                raise UserError(_('Recompute hanya bisa dilakukan saat state Draft/Computed.'))
            rec._compute_revenue()
            rec._compute_direct_cost()
            rec.computed_date = fields.Datetime.now()

    def _clear_auto_lines(self, category_group):
        """Hapus line non-manual (bukan adjustment Finance) untuk grup kategori tertentu,
        supaya Recompute tidak menumpuk duplikat."""
        self.line_ids.filtered(
            lambda l: not l.is_manual_adjustment and l.category_group == category_group
        ).unlink()

    def _create_line(self, cost_category_xmlid, amount, description,
                      source_model=False, source_res_id=False):
        category = self.env.ref('vessel_voyage_pnl.%s' % cost_category_xmlid)
        return self.env['vessel.voyage.pnl.line'].create({
            'pnl_id': self.id,
            'cost_category_id': category.id,
            'amount': amount,
            'description': description,
            'source_model': source_model,
            'source_res_id': source_res_id,
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

        existing_pnl = self.env['vessel.voyage.pnl'].search([('voyage_id', '=', voyage.id)], limit=1)
        if not existing_pnl:
            pnl = self.create({'voyage_id': voyage.id})
            pnl.action_generate_pnl()
        else:
            existing_pnl.action_recompute()
