# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FxReportWizard(models.TransientModel):
    _name = 'fx.report.wizard'
    _description = 'Wizard Konfigurasi Laporan Dual-Currency'

    report_name = fields.Char(
        string='Nama Laporan',
        required=True,
        compute='_compute_report_name',
        store=True,
        readonly=False,
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Perusahaan',
        required=True,
        default=lambda self: self.env.company,
    )

    report_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Mata Uang Presentasi',
        required=True,
        default=lambda self: self.env['res.currency'].search(
            [('name', '=', 'USD')], limit=1
        ),
        domain=[('active', '=', True)],
    )

    pl_date_from = fields.Date(
        string='Periode Dari',
        required=True,
        default=lambda self: fields.Date.today().replace(month=1, day=1),
    )

    pl_date_to = fields.Date(
        string='Periode Sampai',
        required=True,
        default=lambda self: fields.Date.today().replace(month=12, day=31),
    )

    pl_avg_rate = fields.Float(
        string='Kurs Rata-rata P&L (IDR/USD)',
        digits=(16, 4),
        compute='_compute_rates',
        store=True,
        readonly=False,
        help='Auto-hitung dari tabel kurs. Dapat diubah manual.',
    )

    bs_closing_rate = fields.Float(
        string='Kurs Closing Neraca (IDR/USD)',
        digits=(16, 4),
        compute='_compute_rates',
        store=True,
        readonly=False,
        help='Auto-ambil kurs per tanggal Sampai. Dapat diubah manual.',
    )

    rate_source = fields.Selection(
        selection=[
            ('bi_jisdor', 'BI JISDOR'),
            ('manual', 'Manual'),
            ('internal', 'Internal'),
        ],
        string='Sumber Kurs',
        required=True,
        default='manual',
    )

    rate_info = fields.Char(
        string='Info Kurs',
        compute='_compute_rate_info',
        readonly=True,
    )

    existing_config_id = fields.Many2one(
        comodel_name='acc.id.fx.report.config',
        string='Laporan Existing',
        compute='_compute_existing_config',
        help='Laporan dengan periode yang sama yang sudah pernah dihitung.',
    )

    notes = fields.Text(string='Catatan')

    # ── Compute ───────────────────────────────────────────────────────────────

    @api.depends('company_id', 'pl_date_from', 'pl_date_to', 'report_currency_id')
    def _compute_report_name(self):
        for rec in self:
            if rec.pl_date_from and rec.pl_date_to:
                year = rec.pl_date_to.year
                month_from = rec.pl_date_from.strftime('%b')
                month_to = rec.pl_date_to.strftime('%b')
                company_short = (rec.company_id.name or '')[:20]
                if (rec.pl_date_from.month == 1
                        and rec.pl_date_to.month == 12
                        and rec.pl_date_from.year == rec.pl_date_to.year):
                    rec.report_name = (
                        f'Laporan Keuangan {year} — {company_short}'
                    )
                else:
                    rec.report_name = (
                        f'Laporan {month_from}–{month_to} {year}'
                        f' — {company_short}'
                    )
            else:
                rec.report_name = 'Laporan Dual-Currency'

    @api.depends('pl_date_from', 'pl_date_to', 'report_currency_id', 'company_id')
    def _compute_rates(self):
        engine = self.env['acc.id.translation.engine']
        for rec in self:
            if not (rec.pl_date_from and rec.pl_date_to and rec.report_currency_id):
                rec.pl_avg_rate = 0.0
                rec.bs_closing_rate = 0.0
                continue
            try:
                temp = self.env['acc.id.fx.report.config'].new({
                    'company_id': rec.company_id.id,
                    'report_currency_id': rec.report_currency_id.id,
                    'pl_date_from': rec.pl_date_from,
                    'pl_date_to': rec.pl_date_to,
                    'bs_closing_date': rec.pl_date_to,
                })
                rec.pl_avg_rate = engine._compute_average_rate(temp)
                rec.bs_closing_rate = engine._compute_closing_rate(temp)
            except Exception:
                rec.pl_avg_rate = 0.0
                rec.bs_closing_rate = 0.0

    @api.depends('pl_avg_rate', 'bs_closing_rate')
    def _compute_rate_info(self):
        for rec in self:
            if rec.pl_avg_rate and rec.bs_closing_rate:
                rec.rate_info = (
                    f'P&L avg: Rp {rec.pl_avg_rate:,.2f}  |  '
                    f'Neraca closing: Rp {rec.bs_closing_rate:,.2f}'
                )
            else:
                rec.rate_info = (
                    'Kurs belum tersedia — periksa Accounting → '
                    'Konfigurasi → Kurs Mata Uang'
                )

    @api.depends('company_id', 'pl_date_from', 'pl_date_to', 'report_currency_id')
    def _compute_existing_config(self):
        for rec in self:
            if not (rec.company_id and rec.pl_date_from and rec.pl_date_to):
                rec.existing_config_id = False
                continue
            existing = self.env['acc.id.fx.report.config'].search([
                ('company_id', '=', rec.company_id.id),
                ('pl_date_from', '=', rec.pl_date_from),
                ('pl_date_to', '=', rec.pl_date_to),
                ('report_currency_id', '=', rec.report_currency_id.id),
                ('state', '!=', 'draft'),
            ], limit=1, order='last_calculated_at desc')
            rec.existing_config_id = existing

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_calculate_new(self):
        """Buat config baru dan langsung jalankan kalkulasi."""
        self.ensure_one()
        self._validate_wizard()

        config = self.env['acc.id.fx.report.config'].create({
            'name': self.report_name,
            'company_id': self.company_id.id,
            'report_currency_id': self.report_currency_id.id,
            'pl_date_from': self.pl_date_from,
            'pl_date_to': self.pl_date_to,
            'bs_closing_date': self.pl_date_to,
            'pl_avg_rate': self.pl_avg_rate,
            'bs_closing_rate': self.bs_closing_rate,
            'rate_source': self.rate_source,
            'scenario': 'idr_functional',
            'notes': self.notes or False,
        })

        config.action_calculate()

        return {
            'type': 'ir.actions.act_window',
            'name': config.name,
            'res_model': 'acc.id.fx.report.config',
            'res_id': config.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_existing(self):
        """Buka config existing tanpa hitung ulang."""
        self.ensure_one()
        if not self.existing_config_id:
            raise UserError(_('Tidak ada laporan existing yang ditemukan.'))
        return {
            'type': 'ir.actions.act_window',
            'name': self.existing_config_id.name,
            'res_model': 'acc.id.fx.report.config',
            'res_id': self.existing_config_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _validate_wizard(self):
        if self.pl_date_from > self.pl_date_to:
            raise UserError(_(
                'Tanggal "Dari" tidak boleh lebih besar dari tanggal "Sampai".'
            ))
        if not self.pl_avg_rate or self.pl_avg_rate <= 0:
            raise UserError(_(
                'Kurs rata-rata tidak valid. '
                'Pastikan data kurs %s tersedia di sistem '
                'atau isi kurs secara manual.'
            ) % self.report_currency_id.name)
        if not self.bs_closing_rate or self.bs_closing_rate <= 0:
            raise UserError(_(
                'Kurs closing tidak valid. '
                'Pastikan data kurs %s tersedia di sistem '
                'atau isi kurs secara manual.'
            ) % self.report_currency_id.name)
        if self.functional_currency_id == self.report_currency_id:
            raise UserError(_(
                'Mata uang fungsional dan presentasi tidak boleh sama.'
            ))

    @property
    def functional_currency_id(self):
        return self.company_id.currency_id
