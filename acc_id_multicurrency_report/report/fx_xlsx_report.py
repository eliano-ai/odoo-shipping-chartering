# -*- coding: utf-8 -*-
import io
from odoo import models

_INCOME_TYPES = frozenset({'income', 'income_other'})
_EXPENSE_TYPES = frozenset({
    'expense', 'expense_depreciation', 'expense_direct_cost'
})
_ASSET_TYPES = frozenset({
    'asset_cash', 'asset_receivable', 'asset_current',
    'asset_non_current', 'asset_prepayments', 'asset_fixed',
})
_LIABILITY_TYPES = frozenset({
    'liability_payable', 'liability_current', 'liability_non_current',
})
_EQUITY_TYPES = frozenset({'equity', 'equity_unaffected'})


class FxReportXlsx(models.AbstractModel):
    _name = 'report.acc_id_multicurrency_report.fx_report_xlsx'
    _description = 'Export XLSX Laporan Dual-Currency'

    def generate_xlsx_data(self, config):
        """Generate XLSX dan kembalikan sebagai bytes."""
        import xlsxwriter
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        self._setup_formats(workbook)
        self._write_pl_sheet(workbook, config)
        self._write_bs_sheet(workbook, config)
        self._write_info_sheet(workbook, config)
        workbook.close()
        return output.getvalue()

    # ── P&L Sheet ─────────────────────────────────────────────────────────────

    def _write_pl_sheet(self, workbook, config):
        ws = workbook.add_worksheet('Laba Rugi')

        ws.merge_range('A1:E1', config.company_id.name, self.fmt_title)
        ws.merge_range('A2:E2', 'LAPORAN LABA RUGI — MANAJEMEN', self.fmt_title)
        ws.merge_range(
            'A3:E3',
            f"Periode: {config.pl_date_from} – {config.pl_date_to}",
            self.fmt_subtitle,
        )

        headers = ['Kode', 'Uraian', 'IDR (Rp)', 'Kurs', 'USD ($)']
        widths = [12, 45, 22, 12, 20]
        for col, (h, w) in enumerate(zip(headers, widths)):
            ws.write(4, col, h, self.fmt_col_header)
            ws.set_column(col, col, w)

        pl_lines = config.report_line_ids.filtered(
            lambda l: l.report_type == 'pl'
        ).sorted('account_code')

        row = 5

        # Pendapatan
        ws.merge_range(row, 0, row, 4, 'PENDAPATAN USAHA', self.fmt_section)
        row += 1
        t_inc_idr = t_inc_usd = 0.0
        for line in pl_lines.filtered(lambda l: l.account_type in _INCOME_TYPES):
            ws.write(row, 0, line.account_code or '', self.fmt_normal)
            ws.write(row, 1, line.account_name or '', self.fmt_normal)
            ws.write(row, 2, line.balance_functional, self.fmt_idr)
            ws.write(row, 3, line.rate_used, self.fmt_rate)
            ws.write(row, 4, line.balance_presentation, self.fmt_usd)
            t_inc_idr += line.balance_functional
            t_inc_usd += line.balance_presentation
            row += 1
        ws.write(row, 1, 'Jumlah Pendapatan', self.fmt_subtotal_lbl)
        ws.write(row, 2, t_inc_idr, self.fmt_subtotal_idr)
        ws.write(row, 3, 'avg', self.fmt_rate)
        ws.write(row, 4, t_inc_usd, self.fmt_subtotal_usd)
        row += 2

        # Beban
        ws.merge_range(row, 0, row, 4, 'BEBAN USAHA', self.fmt_section)
        row += 1
        t_exp_idr = t_exp_usd = 0.0
        for line in pl_lines.filtered(lambda l: l.account_type in _EXPENSE_TYPES):
            ws.write(row, 0, line.account_code or '', self.fmt_normal)
            ws.write(row, 1, line.account_name or '', self.fmt_normal)
            ws.write(row, 2, line.balance_functional, self.fmt_idr)
            ws.write(row, 3, line.rate_used, self.fmt_rate)
            ws.write(row, 4, line.balance_presentation, self.fmt_usd)
            t_exp_idr += line.balance_functional
            t_exp_usd += line.balance_presentation
            row += 1
        ws.write(row, 1, 'Jumlah Beban Usaha', self.fmt_subtotal_lbl)
        ws.write(row, 2, t_exp_idr, self.fmt_subtotal_idr)
        ws.write(row, 3, 'avg', self.fmt_rate)
        ws.write(row, 4, t_exp_usd, self.fmt_subtotal_usd)
        row += 2

        # Other lines (selisih kurs dll)
        other_lines = pl_lines.filtered(
            lambda l: l.account_type not in _INCOME_TYPES | _EXPENSE_TYPES
        )
        if other_lines:
            ws.merge_range(row, 0, row, 4, 'LAIN-LAIN', self.fmt_section)
            row += 1
            for line in other_lines:
                ws.write(row, 0, line.account_code or '', self.fmt_normal)
                ws.write(row, 1, line.account_name or '', self.fmt_normal)
                ws.write(row, 2, line.balance_functional, self.fmt_idr)
                ws.write(row, 3, line.rate_used, self.fmt_rate)
                ws.write(row, 4, line.balance_presentation, self.fmt_usd)
                t_inc_idr += line.balance_functional
                t_inc_usd += line.balance_presentation
                row += 1
            row += 1

        # Laba Bersih
        net_idr = t_inc_idr + t_exp_idr
        net_usd = t_inc_usd + t_exp_usd
        ws.write(row, 1, 'LABA BERSIH PERIODE', self.fmt_total_lbl)
        ws.write(row, 2, net_idr, self.fmt_total_idr)
        ws.write(row, 3, '', self.fmt_total_lbl)
        ws.write(row, 4, net_usd, self.fmt_total_usd)
        row += 3

        ws.merge_range(row, 0, row, 4, (
            f'*Kolom USD disajikan untuk tujuan informasi manajemen '
            f'menggunakan kurs rata-rata Rp {config.pl_avg_rate:,.2f}/USD. '
            f'Bukan merupakan translasi laporan keuangan PSAK 10.'
        ), self.fmt_disclaimer)

    # ── Balance Sheet Sheet ───────────────────────────────────────────────────

    def _write_bs_sheet(self, workbook, config):
        ws = workbook.add_worksheet('Neraca')

        ws.merge_range('A1:E1', config.company_id.name, self.fmt_title)
        ws.merge_range('A2:E2', 'NERACA — MANAJEMEN', self.fmt_title)
        ws.merge_range(
            'A3:E3',
            f"Per: {config.bs_closing_date}",
            self.fmt_subtitle,
        )

        headers = ['Kode', 'Uraian', 'IDR (Rp)', 'Kurs', 'USD ($)']
        widths = [12, 45, 22, 12, 20]
        for col, (h, w) in enumerate(zip(headers, widths)):
            ws.write(4, col, h, self.fmt_col_header)
            ws.set_column(col, col, w)

        bs_lines = config.report_line_ids.filtered(
            lambda l: l.report_type == 'bs'
        ).sorted('account_code')

        row = 5

        def _write_section(label, line_filter):
            nonlocal row
            section_lines = bs_lines.filtered(line_filter)
            if not section_lines:
                return 0.0, 0.0
            ws.merge_range(row, 0, row, 4, label, self.fmt_section)
            row += 1
            total_idr = total_usd = 0.0
            for line in section_lines:
                ws.write(row, 0, line.account_code or '', self.fmt_normal)
                ws.write(row, 1, line.account_name or '', self.fmt_normal)
                ws.write(row, 2, line.balance_functional, self.fmt_idr)
                ws.write(row, 3, line.rate_used, self.fmt_rate)
                ws.write(row, 4, line.balance_presentation, self.fmt_usd)
                total_idr += line.balance_functional
                total_usd += line.balance_presentation
                row += 1
            return total_idr, total_usd

        ta_idr, ta_usd = _write_section(
            'ASET', lambda l: l.account_type in _ASSET_TYPES
        )
        ws.write(row, 1, 'Jumlah Aset', self.fmt_subtotal_lbl)
        ws.write(row, 2, ta_idr, self.fmt_subtotal_idr)
        ws.write(row, 3, 'closing', self.fmt_rate)
        ws.write(row, 4, ta_usd, self.fmt_subtotal_usd)
        row += 2

        tl_idr, tl_usd = _write_section(
            'LIABILITAS', lambda l: l.account_type in _LIABILITY_TYPES
        )
        ws.write(row, 1, 'Jumlah Liabilitas', self.fmt_subtotal_lbl)
        ws.write(row, 2, tl_idr, self.fmt_subtotal_idr)
        ws.write(row, 3, 'closing', self.fmt_rate)
        ws.write(row, 4, tl_usd, self.fmt_subtotal_usd)
        row += 2

        te_idr, te_usd = _write_section(
            'EKUITAS', lambda l: l.account_type in _EQUITY_TYPES
        )
        ws.write(row, 1, 'Jumlah Ekuitas', self.fmt_subtotal_lbl)
        ws.write(row, 2, te_idr, self.fmt_subtotal_idr)
        ws.write(row, 3, 'closing', self.fmt_rate)
        ws.write(row, 4, te_usd, self.fmt_subtotal_usd)
        row += 2

        tle_idr = tl_idr + te_idr
        tle_usd = tl_usd + te_usd
        ws.write(row, 1, 'JUMLAH LIABILITAS & EKUITAS', self.fmt_total_lbl)
        ws.write(row, 2, tle_idr, self.fmt_total_idr)
        ws.write(row, 3, '', self.fmt_total_lbl)
        ws.write(row, 4, tle_usd, self.fmt_total_usd)
        row += 3

        ws.merge_range(row, 0, row, 4, (
            f'*Kurs closing Rp {config.bs_closing_rate:,.2f}/USD '
            f'(BI JISDOR per {config.bs_closing_date}). '
            f'Bukan merupakan translasi laporan keuangan PSAK 10.'
        ), self.fmt_disclaimer)

    # ── Info Sheet ────────────────────────────────────────────────────────────

    def _write_info_sheet(self, workbook, config):
        ws = workbook.add_worksheet('Info Kurs & Kalkulasi')
        ws.merge_range('A1:B1', 'INFORMASI KALKULASI LAPORAN', self.fmt_title)
        ws.set_column(0, 0, 38)
        ws.set_column(1, 1, 42)

        rate_source_labels = {
            'bi_jisdor': 'BI JISDOR',
            'manual': 'Manual',
            'internal': 'Internal',
        }
        state_labels = {
            'draft': 'Draft',
            'calculated': 'Sudah Dihitung',
            'stale': 'Data Berubah',
        }

        info_rows = [
            ('Nama Laporan', config.name or ''),
            ('Perusahaan', config.company_id.name or ''),
            ('Mata Uang Fungsional', config.functional_currency_id.name or ''),
            ('Mata Uang Presentasi', config.report_currency_id.name or ''),
            ('Periode P&L Dari', str(config.pl_date_from)),
            ('Periode P&L Sampai', str(config.pl_date_to)),
            ('Tanggal Closing Neraca', str(config.bs_closing_date)),
            ('Kurs Rata-rata P&L (IDR/USD)', f"Rp {config.pl_avg_rate:,.4f}"),
            ('Kurs Closing Neraca (IDR/USD)', f"Rp {config.bs_closing_rate:,.4f}"),
            ('Sumber Kurs',
             rate_source_labels.get(config.rate_source, config.rate_source or '')),
            ('Tanggal Dihitung',
             config.last_calculated_at.strftime('%d %b %Y %H:%M WIB')
             if config.last_calculated_at else '-'),
            ('Dihitung Oleh',
             config.last_calculated_by.name if config.last_calculated_by else '-'),
            ('Jumlah Baris P&L', config.pl_line_count),
            ('Jumlah Baris Neraca', config.bs_line_count),
            ('Status Laporan', state_labels.get(config.state, config.state or '')),
            ('Skenario', config.scenario or ''),
            ('Catatan', config.notes or '-'),
        ]

        for r, (label, value) in enumerate(info_rows, start=2):
            ws.write(r, 0, label, self.fmt_col_header)
            ws.write(r, 1, value, self.fmt_normal)

        last_row = len(info_rows) + 4
        ws.merge_range(last_row, 0, last_row, 1, (
            'Laporan ini disajikan untuk tujuan informasi manajemen internal. '
            'Penyajian kolom USD bukan merupakan translasi laporan keuangan '
            'sebagaimana dimaksud dalam PSAK 10 (Pengaruh Perubahan Kurs '
            'Valuta Asing) dan tidak dimaksudkan untuk memenuhi persyaratan '
            'pelaporan statutory kepada regulator manapun.'
        ), self.fmt_disclaimer)

    # ── Format Setup ──────────────────────────────────────────────────────────

    def _setup_formats(self, workbook):
        self.fmt_title = workbook.add_format({
            'bold': True, 'font_size': 13,
            'align': 'center', 'valign': 'vcenter',
        })
        self.fmt_subtitle = workbook.add_format({
            'font_size': 10, 'align': 'center', 'color': '#555555',
        })
        self.fmt_col_header = workbook.add_format({
            'bold': True, 'bg_color': '#1F3864', 'font_color': '#FFFFFF',
            'align': 'center', 'valign': 'vcenter', 'border': 1,
            'font_size': 10,
        })
        self.fmt_section = workbook.add_format({
            'bold': True, 'bg_color': '#D9E1F2', 'border': 1,
            'font_size': 10,
        })
        self.fmt_normal = workbook.add_format({'border': 1, 'font_size': 10})
        self.fmt_idr = workbook.add_format({
            'num_format': '#,##0', 'border': 1,
            'align': 'right', 'font_size': 10,
        })
        self.fmt_usd = workbook.add_format({
            'num_format': '#,##0.00', 'border': 1,
            'align': 'right', 'font_size': 10,
        })
        self.fmt_rate = workbook.add_format({
            'num_format': '#,##0.00', 'border': 1,
            'align': 'center', 'font_size': 9, 'color': '#666666',
        })
        self.fmt_subtotal_lbl = workbook.add_format({
            'bold': True, 'border': 1, 'top': 2, 'font_size': 10,
        })
        self.fmt_subtotal_idr = workbook.add_format({
            'bold': True, 'num_format': '#,##0',
            'border': 1, 'top': 2, 'align': 'right', 'font_size': 10,
        })
        self.fmt_subtotal_usd = workbook.add_format({
            'bold': True, 'num_format': '#,##0.00',
            'border': 1, 'top': 2, 'align': 'right', 'font_size': 10,
        })
        self.fmt_total_lbl = workbook.add_format({
            'bold': True, 'bg_color': '#1F3864', 'font_color': '#FFFFFF',
            'border': 1, 'font_size': 11,
        })
        self.fmt_total_idr = workbook.add_format({
            'bold': True, 'bg_color': '#1F3864', 'font_color': '#FFFFFF',
            'num_format': '#,##0', 'border': 1,
            'align': 'right', 'font_size': 11,
        })
        self.fmt_total_usd = workbook.add_format({
            'bold': True, 'bg_color': '#1F3864', 'font_color': '#FFFFFF',
            'num_format': '#,##0.00', 'border': 1,
            'align': 'right', 'font_size': 11,
        })
        self.fmt_disclaimer = workbook.add_format({
            'italic': True, 'font_size': 8, 'color': '#777777',
            'text_wrap': True, 'valign': 'top',
        })