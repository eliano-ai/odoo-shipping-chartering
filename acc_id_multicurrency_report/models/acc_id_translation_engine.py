# -*- coding: utf-8 -*-
import time
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Tipe akun Odoo 18 — P&L
_PL_ACCOUNT_TYPES = (
    'income', 'income_other',
    'expense', 'expense_depreciation', 'expense_direct_cost',
)

# Tipe akun Odoo 18 — Balance Sheet
_BS_ACCOUNT_TYPES = (
    'asset_cash', 'asset_receivable', 'asset_current',
    'asset_non_current', 'asset_prepayments', 'asset_fixed',
    'liability_payable', 'liability_current', 'liability_non_current',
    'equity', 'equity_unaffected',
)


class AccIdTranslationEngine(models.AbstractModel):
    _name = 'acc.id.translation.engine'
    _description = 'Engine Kalkulasi Dual-Currency'

    # ═══════════════════════════════════════════════════════════════════════════
    # PUBLIC ENTRY POINT
    # ═══════════════════════════════════════════════════════════════════════════

    def run_calculation(self, config):
        """
        Entry point utama kalkulasi laporan dual-currency.
        Dipanggil dari acc.id.fx.report.config.action_calculate().

        Flow:
          1. Resolve kurs (average + closing)
          2. Simpan kurs ke config
          3. Hapus lines lama
          4. Compute lines baru (sesuai skenario)
          5. Bulk create lines
          6. Buat calc log (immutable)
          7. Update state config
        """
        config.ensure_one()
        start_time = time.time()

        _logger.info(
            'FX Calculation START | config=%d | company=%s | period=%s to %s',
            config.id, config.company_id.name,
            config.pl_date_from, config.pl_date_to,
        )

        try:
            # Step 1: Resolve kurs
            avg_rate, closing_rate = self._resolve_rates(config)

            # Step 2: Simpan kurs yang digunakan ke config
            # Gunakan sudo agar tidak terhalang access rule di write
            config.sudo().write({
                'pl_avg_rate': avg_rate,
                'bs_closing_rate': closing_rate,
            })

            # Step 3: Hapus lines lama
            config.report_line_ids.unlink()

            # Step 4: Compute berdasarkan skenario
            if config.scenario == 'idr_functional':
                lines_data = self._compute_idr_functional(
                    config, avg_rate, closing_rate
                )
            else:
                raise UserError(_(
                    'Skenario "USD Functional" (PSAK 10 penuh) '
                    'akan tersedia di Phase 3 pengembangan modul ini.'
                ))

            # Step 5: Bulk create untuk performa
            self.env['acc.id.fx.report.line'].create(lines_data)

            duration = round(time.time() - start_time, 2)

            # Step 6: Buat log immutable
            log = self.env['acc.id.fx.calc.log'].sudo().create({
                'config_id': config.id,
                'run_at': fields.Datetime.now(),
                'run_by': self.env.user.id,
                'pl_avg_rate_used': avg_rate,
                'bs_closing_rate_used': closing_rate,
                'rate_source': config.rate_source or 'manual',
                'lines_computed': len(lines_data),
                'duration_seconds': duration,
                'trigger_reason': 'manual',
                'result': 'success',
                'notes': _(
                    'Kalkulasi berhasil. %d baris diproses dalam %.2f detik.'
                ) % (len(lines_data), duration),
            })

            # Update calc_log_id di semua lines yang baru dibuat
            config.report_line_ids.write({'calc_log_id': log.id})

            # Step 7: Update state config
            config.sudo().write({
                'state': 'calculated',
                'last_calculated_at': fields.Datetime.now(),
                'last_calculated_by': self.env.user.id,
                'is_stale': False,
                'stale_reason': False,
            })

            _logger.info(
                'FX Calculation DONE | config=%d | lines=%d | duration=%.2fs',
                config.id, len(lines_data), duration,
            )

        except Exception as exc:
            duration = round(time.time() - start_time, 2)
            # Log error — tetap dibuat meski kalkulasi gagal
            try:
                self.env['acc.id.fx.calc.log'].sudo().create({
                    'config_id': config.id,
                    'run_at': fields.Datetime.now(),
                    'run_by': self.env.user.id,
                    'pl_avg_rate_used': config.pl_avg_rate or 0.0,
                    'bs_closing_rate_used': config.bs_closing_rate or 0.0,
                    'rate_source': config.rate_source or 'manual',
                    'lines_computed': 0,
                    'duration_seconds': duration,
                    'trigger_reason': 'manual',
                    'result': 'error',
                    'error_message': str(exc),
                })
            except Exception:
                pass  # Jangan biarkan logging error menghentikan propagasi exc utama
            _logger.exception('FX Calculation ERROR | config=%d', config.id)
            raise

    # ═══════════════════════════════════════════════════════════════════════════
    # RATE RESOLUTION
    # ═══════════════════════════════════════════════════════════════════════════

    def _resolve_rates(self, config):
        """
        Resolve kurs rata-rata dan closing.
        Jika config sudah punya nilai (manual override), gunakan itu.
        Return: (avg_rate, closing_rate) — keduanya dalam market rate IDR/USD.
        """
        avg_rate = (
            config.pl_avg_rate
            if config.pl_avg_rate and config.pl_avg_rate > 0
            else self._compute_average_rate(config)
        )
        closing_rate = (
            config.bs_closing_rate
            if config.bs_closing_rate and config.bs_closing_rate > 0
            else self._compute_closing_rate(config)
        )
        return avg_rate, closing_rate

    def _compute_average_rate(self, config):
        """
        Hitung rata-rata aritmetika kurs dalam rentang [pl_date_from, pl_date_to].

        Konvensi kurs Odoo 18 dengan company=IDR, currency=USD:
          res.currency.rate.rate = jumlah IDR per 1 USD (market rate langsung)

        Fallback bertingkat:
          1. Rata-rata semua kurs dalam periode
          2. Kurs terakhir sebelum pl_date_from
          3. UserError jika tidak ada sama sekali
        """
        CurrencyRate = self.env['res.currency.rate']

        rates = CurrencyRate.search([
            ('currency_id', '=', config.report_currency_id.id),
            ('name', '>=', config.pl_date_from),
            ('name', '<=', config.pl_date_to),
            ('company_id', 'in', [config.company_id.id, False]),
        ], order='name asc')

        if rates:
            market_rates = rates.mapped('rate')
            avg = sum(market_rates) / len(market_rates)
            _logger.debug(
                'FX avg rate: %d data points, avg=%.4f', len(market_rates), avg
            )
            return avg

        # Fallback: kurs terakhir sebelum periode
        fallback = CurrencyRate.search([
            ('currency_id', '=', config.report_currency_id.id),
            ('name', '<', config.pl_date_from),
            ('company_id', 'in', [config.company_id.id, False]),
        ], limit=1, order='name desc')

        if fallback:
            _logger.warning(
                'FX: Tidak ada kurs dalam periode %s–%s. '
                'Fallback ke kurs %s (%.4f).',
                config.pl_date_from, config.pl_date_to,
                fallback.name, fallback.rate,
            )
            try:
                config.message_post(body=_(
                    'Peringatan: Tidak ada data kurs USD dalam periode laporan. '
                    'Menggunakan kurs terakhir yang tersedia (%s: Rp %.2f) '
                    'sebagai kurs rata-rata.'
                ) % (fallback.name, fallback.rate))
            except Exception:
                pass
            return fallback.rate

        raise UserError(_(
            'Tidak ada data kurs %s/IDR untuk periode %s – %s.\n\n'
            'Harap input kurs terlebih dahulu di:\n'
            'Accounting → Konfigurasi → Kurs Mata Uang'
        ) % (
            config.report_currency_id.name,
            config.pl_date_from,
            config.pl_date_to,
        ))

    def _compute_closing_rate(self, config):
        """
        Ambil kurs closing: kurs terakhir pada atau sebelum bs_closing_date.
        Beri warning ke chatter jika gap > 5 hari kalender.
        """
        CurrencyRate = self.env['res.currency.rate']

        closing = CurrencyRate.search([
            ('currency_id', '=', config.report_currency_id.id),
            ('name', '<=', config.bs_closing_date),
            ('company_id', 'in', [config.company_id.id, False]),
        ], limit=1, order='name desc')

        if not closing:
            raise UserError(_(
                'Tidak ada data kurs %s/IDR pada atau sebelum %s.\n\n'
                'Harap input kurs terlebih dahulu di:\n'
                'Accounting → Konfigurasi → Kurs Mata Uang'
            ) % (config.report_currency_id.name, config.bs_closing_date))

        # Cek gap — warning jika > 5 hari kalender (≈ 3 hari kerja)
        gap_days = (config.bs_closing_date - closing.name).days
        if gap_days > 5:
            warning = _(
                'Peringatan: Kurs closing diambil dari %s '
                '(%d hari sebelum tanggal penutup %s). '
                'Pertimbangkan untuk menginput kurs yang lebih terkini.'
            ) % (closing.name, gap_days, config.bs_closing_date)
            try:
                config.message_post(body=warning)
            except Exception:
                pass
            _logger.warning('FX closing rate gap: %s', warning)

        return closing.rate

    # ═══════════════════════════════════════════════════════════════════════════
    # SCENARIO: IDR FUNCTIONAL (Phase 1–2)
    # ═══════════════════════════════════════════════════════════════════════════

    def _compute_idr_functional(self, config, avg_rate, closing_rate):
        """
        Skenario re-presentation: IDR (fungsional) → USD (presentasi).
        Semua saldo sudah dalam IDR; dibagi kurs yang sesuai per tipe akun.

        Return: list[dict] siap untuk bulk create acc.id.fx.report.line
        """
        lines_data = []

        # Build override lookup {account_id (int): override_record}
        overrides = {
            ov.account_id.id: ov
            for ov in config.rate_override_ids
        }

        # Ambil saldo per akun via SQL langsung untuk performa
        pl_balances = self._get_account_balances(config, report_type='pl')
        bs_balances = self._get_account_balances(config, report_type='bs')

        # Preload akun agar tidak N+1 query
        all_account_ids = list(set(
            list(pl_balances.keys()) + list(bs_balances.keys())
        ))
        accounts_by_id = {
            acc.id: acc
            for acc in self.env['account.account'].browse(all_account_ids)
        }

        # Process P&L lines
        for account_id, balance_idr in pl_balances.items():
            account = accounts_by_id.get(account_id)
            if not account or account.id_exclude_from_fx:
                continue

            rate_type, rate_val, is_override, override_reason = (
                self._resolve_account_rate(
                    account, overrides, 'pl', avg_rate, closing_rate
                )
            )
            balance_usd = self._to_presentation(balance_idr, rate_val)

            lines_data.append({
                'config_id': config.id,
                'account_id': account_id,
                'report_type': 'pl',
                'balance_functional': balance_idr,
                'rate_type_applied': rate_type,
                'rate_used': rate_val,
                'balance_presentation': balance_usd,
                'is_override': is_override,
                'override_reason': override_reason or False,
            })

        # Process BS lines
        for account_id, balance_idr in bs_balances.items():
            account = accounts_by_id.get(account_id)
            if not account or account.id_exclude_from_fx:
                continue

            rate_type, rate_val, is_override, override_reason = (
                self._resolve_account_rate(
                    account, overrides, 'bs', avg_rate, closing_rate
                )
            )
            balance_usd = self._to_presentation(balance_idr, rate_val)

            lines_data.append({
                'config_id': config.id,
                'account_id': account_id,
                'report_type': 'bs',
                'balance_functional': balance_idr,
                'rate_type_applied': rate_type,
                'rate_used': rate_val,
                'balance_presentation': balance_usd,
                'is_override': is_override,
                'override_reason': override_reason or False,
            })

        return lines_data

    def _get_account_balances(self, config, report_type):
        """
        Query saldo per akun menggunakan SQL langsung untuk performa optimal.
        Menghindari N+1 ORM query pada dataset besar.

        P&L  → transaksi dalam [pl_date_from, pl_date_to]
        BS   → akumulasi dari awal waktu s/d bs_closing_date

        Return: dict {account_id: balance_idr}
        """
        cr = self.env.cr

        if report_type == 'pl':
            cr.execute("""
                SELECT
                    aml.account_id,
                    SUM(aml.balance) AS balance
                FROM account_move_line aml
                JOIN account_account   aa ON aa.id  = aml.account_id
                JOIN account_move      am ON am.id  = aml.move_id
                WHERE
                    am.state        = 'posted'
                    AND am.company_id = %(company_id)s
                    AND aml.date   >= %(date_from)s
                    AND aml.date   <= %(date_to)s
                    AND aa.account_type = ANY(%(account_types)s)
                    AND (aa.id_exclude_from_fx IS NULL
                         OR aa.id_exclude_from_fx = FALSE)
                GROUP BY aml.account_id
                HAVING SUM(aml.balance) <> 0
            """, {
                'company_id': config.company_id.id,
                'date_from': config.pl_date_from,
                'date_to': config.pl_date_to,
                'account_types': list(_PL_ACCOUNT_TYPES),
            })
        else:  # bs
            cr.execute("""
                SELECT
                    aml.account_id,
                    SUM(aml.balance) AS balance
                FROM account_move_line aml
                JOIN account_account   aa ON aa.id  = aml.account_id
                JOIN account_move      am ON am.id  = aml.move_id
                WHERE
                    am.state        = 'posted'
                    AND am.company_id = %(company_id)s
                    AND aml.date   <= %(date_to)s
                    AND aa.account_type = ANY(%(account_types)s)
                    AND (aa.id_exclude_from_fx IS NULL
                         OR aa.id_exclude_from_fx = FALSE)
                GROUP BY aml.account_id
                HAVING SUM(aml.balance) <> 0
            """, {
                'company_id': config.company_id.id,
                'date_to': config.bs_closing_date,
                'account_types': list(_BS_ACCOUNT_TYPES),
            })

        return {row['account_id']: row['balance'] for row in cr.dictfetchall()}

    def _resolve_account_rate(
        self, account, overrides, report_type, avg_rate, closing_rate
    ):
        """
        Tentukan kurs yang digunakan untuk satu akun.

        Urutan prioritas:
          1. Override eksplisit di acc.id.fx.rate.override
          2. Field id_fx_rate_type di account.account
          3. Default berdasarkan account_type

        Return: (rate_type_str, rate_value, is_override, override_reason)
        """
        # Prioritas 1: override per akun
        if account.id in overrides:
            ov = overrides[account.id]
            if ov.rate_type_override == 'manual':
                return ('closing', ov.manual_rate, True, ov.reason)
            elif ov.rate_type_override == 'average':
                return ('average', avg_rate, True, ov.reason)
            elif ov.rate_type_override == 'closing':
                return ('closing', closing_rate, True, ov.reason)
            # historical: di Phase 1 fallback ke closing
            return ('closing', closing_rate, True, ov.reason)

        # Prioritas 2 + 3: effective rate type dari akun
        effective_type = account._get_effective_fx_rate_type()

        if effective_type == 'average':
            return ('average', avg_rate, False, None)
        elif effective_type == 'actual':
            # Untuk akun selisih kurs: gunakan avg_rate sebagai approx
            return ('actual', avg_rate, False, None)
        elif effective_type == 'historical':
            # Phase 1: historical fallback ke closing
            # Phase 3 akan implement per-transaction historical rate
            return ('closing', closing_rate, False, None)
        else:
            return ('closing', closing_rate, False, None)

    @staticmethod
    def _to_presentation(balance_idr, market_rate):
        """
        Konversi saldo IDR ke USD menggunakan market rate.

        Args:
            balance_idr   : saldo dalam IDR (bisa negatif)
            market_rate   : kurs pasar IDR per 1 USD (contoh: 16000.0)

        Return: saldo dalam USD (float), 0.0 jika rate tidak valid
        """
        if not market_rate or market_rate == 0:
            return 0.0
        return balance_idr / market_rate
