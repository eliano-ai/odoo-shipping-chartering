# -*- coding: utf-8 -*-
import base64
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AccIdFxReportConfig(models.Model):
    _name = 'acc.id.fx.report.config'
    _description = 'Konfigurasi Laporan Dual-Currency'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'pl_date_to desc, id desc'
    _rec_name = 'name'

    # ── Identitas ─────────────────────────────────────────────────────────────

    name = fields.Char(
        string='Nama Laporan',
        required=True,
        tracking=True,
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Perusahaan',
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )

    functional_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Mata Uang Fungsional',
        related='company_id.currency_id',
        store=True,
        readonly=True,
    )

    report_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Mata Uang Presentasi',
        required=True,
        default=lambda self: self.env['res.currency'].search(
            [('name', '=', 'USD')], limit=1
        ),
        tracking=True,
        domain=[('active', '=', True)],
    )

    scenario = fields.Selection(
        selection=[
            ('idr_functional', 'IDR Fungsional — Re-presentation Manajemen'),
            ('usd_functional', 'USD Fungsional — Translasi PSAK 10 (Phase 3)'),
        ],
        string='Skenario',
        default='idr_functional',
        required=True,
        tracking=True,
    )

    # ── Periode ───────────────────────────────────────────────────────────────

    pl_date_from = fields.Date(
        string='Periode P&L — Dari',
        required=True,
        tracking=True,
    )

    pl_date_to = fields.Date(
        string='Periode P&L — Sampai',
        required=True,
        tracking=True,
    )

    bs_closing_date = fields.Date(
        string='Tanggal Closing Neraca',
        required=True,
        tracking=True,
        help='Umumnya sama dengan Periode P&L — Sampai.',
    )

    # ── Kurs ──────────────────────────────────────────────────────────────────

    pl_avg_rate = fields.Float(
        string='Kurs Rata-rata P&L (IDR/USD)',
        digits=(16, 4),
        tracking=True,
        help=(
            'Kurs pasar rata-rata periode (IDR per 1 USD).\n'
            'Contoh: 15987.50 → USD 1 = Rp 15.987,50.\n'
            'Auto-hitung dari tabel kurs, dapat di-override manual.'
        ),
    )

    bs_closing_rate = fields.Float(
        string='Kurs Closing Neraca (IDR/USD)',
        digits=(16, 4),
        tracking=True,
        help=(
            'Kurs pasar pada tanggal closing neraca (IDR per 1 USD).\n'
            'Auto-ambil dari tabel kurs, dapat di-override manual.'
        ),
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
        tracking=True,
    )

    rate_override_note = fields.Text(
        string='Catatan Override Kurs',
        help='Wajib diisi jika kurs di-override secara manual.',
    )

    # ── Status ────────────────────────────────────────────────────────────────

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('calculated', 'Sudah Dihitung'),
            ('stale', 'Data Berubah'),
        ],
        string='Status',
        default='draft',
        readonly=True,
        tracking=True,
    )

    last_calculated_at = fields.Datetime(
        string='Terakhir Dihitung',
        readonly=True,
    )

    last_calculated_by = fields.Many2one(
        comodel_name='res.users',
        string='Dihitung Oleh',
        readonly=True,
    )

    is_stale = fields.Boolean(
        string='Data Berubah',
        default=False,
    )

    stale_reason = fields.Text(
        string='Alasan Stale',
        readonly=True,
    )

    notes = fields.Text(string='Catatan')

    # ── Relasi ────────────────────────────────────────────────────────────────

    report_line_ids = fields.One2many(
        comodel_name='acc.id.fx.report.line',
        inverse_name='config_id',
        string='Baris Laporan',
    )

    calc_log_ids = fields.One2many(
        comodel_name='acc.id.fx.calc.log',
        inverse_name='config_id',
        string='Log Kalkulasi',
    )

    rate_override_ids = fields.One2many(
        comodel_name='acc.id.fx.rate.override',
        inverse_name='config_id',
        string='Override Kurs per Akun',
    )

    # ── Computed ──────────────────────────────────────────────────────────────

    pl_line_count = fields.Integer(
        string='Jumlah Baris P&L',
        compute='_compute_line_counts',
    )

    bs_line_count = fields.Integer(
        string='Jumlah Baris Neraca',
        compute='_compute_line_counts',
    )

    @api.depends('report_line_ids.report_type')
    def _compute_line_counts(self):
        for rec in self:
            rec.pl_line_count = len(
                rec.report_line_ids.filtered(lambda l: l.report_type == 'pl')
            )
            rec.bs_line_count = len(
                rec.report_line_ids.filtered(lambda l: l.report_type == 'bs')
            )

    # ── Constraints ───────────────────────────────────────────────────────────

    @api.constrains('pl_date_from', 'pl_date_to')
    def _check_dates(self):
        for rec in self:
            if rec.pl_date_from and rec.pl_date_to:
                if rec.pl_date_from > rec.pl_date_to:
                    raise ValidationError(_(
                        'Tanggal "Dari" harus lebih kecil atau sama '
                        'dengan tanggal "Sampai".'
                    ))

    @api.constrains('pl_avg_rate', 'bs_closing_rate')
    def _check_rates_positive(self):
        for rec in self:
            if rec.pl_avg_rate and rec.pl_avg_rate <= 0:
                raise ValidationError(_('Kurs rata-rata harus lebih besar dari 0.'))
            if rec.bs_closing_rate and rec.bs_closing_rate <= 0:
                raise ValidationError(_('Kurs closing harus lebih besar dari 0.'))

    @api.constrains('functional_currency_id', 'report_currency_id')
    def _check_different_currencies(self):
        for rec in self:
            if (rec.functional_currency_id
                    and rec.report_currency_id
                    and rec.functional_currency_id == rec.report_currency_id):
                raise ValidationError(_(
                    'Mata uang fungsional dan presentasi tidak boleh sama.'
                ))

    # ── Onchange ──────────────────────────────────────────────────────────────

    @api.onchange('pl_date_to')
    def _onchange_pl_date_to(self):
        if self.pl_date_to and not self.bs_closing_date:
            self.bs_closing_date = self.pl_date_to

    # ── Override write ────────────────────────────────────────────────────────

    def write(self, vals):
        """
        Jika kurs diubah manual setelah state = calculated,
        otomatis set state ke stale agar user tahu perlu hitung ulang.
        """
        rate_fields = {'pl_avg_rate', 'bs_closing_rate', 'rate_source'}
        if any(f in vals for f in rate_fields):
            for rec in self:
                if rec.state == 'calculated':
                    vals.setdefault('state', 'stale')
                    vals.setdefault('stale_reason', _(
                        'Kurs diubah manual pada %s oleh %s.'
                    ) % (
                        fields.Datetime.now().strftime('%d %b %Y %H:%M'),
                        self.env.user.name,
                    ))
        return super().write(vals)

    # ── Stale Detection ───────────────────────────────────────────────────────

    def check_and_update_stale(self):
        """
        Cek apakah ada perubahan data sejak kalkulasi terakhir.
        Dipanggil saat laporan dibuka via controller.
        Update state dan stale_reason jika perlu.
        Return: True jika stale.
        """
        self.ensure_one()
        if self.state == 'draft' or not self.last_calculated_at:
            return False

        new_move_count = self.env['account.move.line'].search_count([
            ('date', '>=', self.pl_date_from),
            ('date', '<=', self.pl_date_to),
            ('move_id.state', '=', 'posted'),
            ('write_date', '>', self.last_calculated_at),
            ('company_id', '=', self.company_id.id),
        ])

        new_rate_count = self.env['res.currency.rate'].search_count([
            ('currency_id', '=', self.report_currency_id.id),
            ('name', '>=', self.pl_date_from),
            ('name', '<=', self.pl_date_to),
            ('write_date', '>', self.last_calculated_at),
            ('company_id', 'in', [self.company_id.id, False]),
        ])

        reasons = []
        if new_move_count:
            reasons.append(_(
                '%d transaksi baru/diubah dalam periode laporan'
            ) % new_move_count)
        if new_rate_count:
            reasons.append(_('data kurs diperbarui'))

        if reasons:
            stale_msg = (
                _('Data berubah setelah kalkulasi terakhir (%s): ')
                % self.last_calculated_at.strftime('%d %b %Y %H:%M')
            ) + ' dan '.join(reasons) + '.'
            self.sudo().write({
                'state': 'stale',
                'is_stale': True,
                'stale_reason': stale_msg,
            })
            return True

        return False

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_calculate(self):
        """
        Entry point kalkulasi laporan.
        Dipanggil dari tombol 'Hitung Laporan' di form atau wizard.
        """
        self.ensure_one()
        self._validate_before_calculate()
        self.env['acc.id.translation.engine'].run_calculation(self)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Laporan: %s') % self.name,
            'res_model': 'acc.id.fx.report.config',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_pl_report(self):
        self.ensure_one()
        if self.state == 'draft':
            raise UserError(_(
                'Laporan belum dihitung. '
                'Klik "Hitung Laporan" terlebih dahulu.'
            ))
        return {
            'type': 'ir.actions.act_url',
            'url': '/acc_id_fx/pl_report/%d' % self.id,
            'target': 'new',
        }

    def action_open_bs_report(self):
        self.ensure_one()
        if self.state == 'draft':
            raise UserError(_(
                'Laporan belum dihitung. '
                'Klik "Hitung Laporan" terlebih dahulu.'
            ))
        return {
            'type': 'ir.actions.act_url',
            'url': '/acc_id_fx/bs_report/%d' % self.id,
            'target': 'new',
        }

    def action_export_xlsx(self):
        self.ensure_one()
        if self.state == 'draft':
            raise UserError(_('Laporan belum dihitung.'))
        xlsx_data = self.env[
            'report.acc_id_multicurrency_report.fx_report_xlsx'
        ].generate_xlsx_data(self)
        filename = (self.name or 'LaporanDualCurrency').replace(' ', '_') + '.xlsx'
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(xlsx_data).decode(),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%d?download=true' % attachment.id,
            'target': 'self',
        }

    def _validate_before_calculate(self):
        self.ensure_one()
        if not self.pl_date_from or not self.pl_date_to:
            raise UserError(_('Periode laporan harus diisi.'))
        if self.pl_date_from > self.pl_date_to:
            raise UserError(_(
                'Tanggal "Dari" tidak boleh lebih besar dari tanggal "Sampai".'
            ))
        if not self.report_currency_id:
            raise UserError(_('Mata uang presentasi harus dipilih.'))
        if self.functional_currency_id == self.report_currency_id:
            raise UserError(_(
                'Mata uang fungsional dan presentasi tidak boleh sama.'
            ))
