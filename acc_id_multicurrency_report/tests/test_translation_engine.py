# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError
from datetime import date


@tagged('post_install', '-at_install', 'fx_report', 'fx_engine')
class TestTranslationEngine(TransactionCase):
    """
    Unit test untuk acc.id.translation.engine — Phase 1.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref('base.main_company')
        cls.usd = cls.env.ref('base.USD')

        # Pastikan USD aktif
        cls.usd.active = True

        # Buat kurs test untuk 2024
        cls._create_test_rates()

        # Buat akun test
        cls._create_test_accounts()

        # Buat jurnal test
        cls._create_test_journal_entries()

    @classmethod
    def _create_test_rates(cls):
        CurrencyRate = cls.env['res.currency.rate']
        # Hapus kurs USD lama di periode test agar tidak bentrok
        CurrencyRate.search([
            ('currency_id', '=', cls.usd.id),
            ('name', '>=', date(2024, 1, 1)),
            ('name', '<=', date(2024, 12, 31)),
            ('company_id', '=', cls.company.id),
        ]).unlink()

        test_rates = [
            (date(2024, 1, 31),  15550.0),
            (date(2024, 3, 31),  15720.0),
            (date(2024, 6, 30),  16043.0),
            (date(2024, 9, 30),  15920.0),
            (date(2024, 12, 31), 16102.0),
        ]
        for d, rate in test_rates:
            CurrencyRate.create({
                'currency_id': cls.usd.id,
                'name': d,
                'rate': rate,
                'rate_source': 'manual',
                'company_id': cls.company.id,
            })

    @classmethod
    def _create_test_accounts(cls):
        AccountAccount = cls.env['account.account']
        cls.account_revenue = AccountAccount.create({
            'code': 'TEST-4100',
            'name': 'Test Revenue FX',
            'account_type': 'income',
            'company_id': cls.company.id,
        })
        cls.account_expense = AccountAccount.create({
            'code': 'TEST-5100',
            'name': 'Test Expense FX',
            'account_type': 'expense',
            'company_id': cls.company.id,
        })
        cls.account_cash = cls.env['account.account'].search([
            ('account_type', '=', 'asset_cash'),
            ('company_id', '=', cls.company.id),
        ], limit=1)

    @classmethod
    def _create_test_journal_entries(cls):
        journal = cls.env['account.journal'].search([
            ('type', '=', 'general'),
            ('company_id', '=', cls.company.id),
        ], limit=1)
        if not journal:
            journal = cls.env['account.journal'].create({
                'name': 'Test FX Journal',
                'type': 'general',
                'code': 'TFXJ',
                'company_id': cls.company.id,
            })

        move = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': date(2024, 6, 15),
            'journal_id': journal.id,
            'company_id': cls.company.id,
            'line_ids': [
                (0, 0, {
                    'account_id': cls.account_cash.id,
                    'debit': 100_000_000.0,
                    'credit': 0.0,
                    'name': 'Test debit',
                }),
                (0, 0, {
                    'account_id': cls.account_revenue.id,
                    'debit': 0.0,
                    'credit': 100_000_000.0,
                    'name': 'Test revenue',
                }),
            ],
        })
        move.action_post()
        cls.test_move = move

    # ── Helper ────────────────────────────────────────────────────────────────

    def _make_config(self, date_from='2024-01-01', date_to='2024-12-31'):
        return self.env['acc.id.fx.report.config'].create({
            'name': f'Test Config {date_from}–{date_to}',
            'company_id': self.company.id,
            'report_currency_id': self.usd.id,
            'pl_date_from': date_from,
            'pl_date_to': date_to,
            'bs_closing_date': date_to,
            'rate_source': 'manual',
            'scenario': 'idr_functional',
        })

    # ── Test: Average Rate ────────────────────────────────────────────────────

    def test_average_rate_computes_correctly(self):
        """Average rate = rata-rata aritmetika semua kurs dalam periode."""
        config = self._make_config()
        engine = self.env['acc.id.translation.engine']
        avg = engine._compute_average_rate(config)

        expected = (15550 + 15720 + 16043 + 15920 + 16102) / 5
        self.assertAlmostEqual(avg, expected, places=2,
            msg='Average rate harus rata-rata dari semua kurs dalam periode')

    def test_average_rate_fallback_to_last_before_period(self):
        """Jika tidak ada kurs dalam periode, gunakan kurs terakhir sebelumnya."""
        config = self._make_config('2025-01-01', '2025-06-30')
        engine = self.env['acc.id.translation.engine']
        avg = engine._compute_average_rate(config)
        # Kurs terakhir sebelum 2025-01-01 adalah 2024-12-31 = 16102
        self.assertEqual(avg, 16102.0)

    def test_average_rate_raises_if_no_data(self):
        """UserError jika tidak ada kurs sama sekali untuk periode itu."""
        config = self._make_config('2010-01-01', '2010-12-31')
        engine = self.env['acc.id.translation.engine']
        with self.assertRaises(UserError):
            engine._compute_average_rate(config)

    # ── Test: Closing Rate ────────────────────────────────────────────────────

    def test_closing_rate_exact_date(self):
        """Closing rate diambil tepat dari tanggal bs_closing_date."""
        config = self._make_config('2024-01-01', '2024-12-31')
        engine = self.env['acc.id.translation.engine']
        closing = engine._compute_closing_rate(config)
        self.assertEqual(closing, 16102.0)

    def test_closing_rate_takes_nearest_before(self):
        """Jika tidak ada kurs tepat di tanggal, ambil yang terakhir sebelumnya."""
        config = self._make_config('2024-01-01', '2024-11-15')
        engine = self.env['acc.id.translation.engine']
        # Tidak ada kurs di 2024-11-15 → ambil 2024-09-30 = 15920
        closing = engine._compute_closing_rate(config)
        self.assertEqual(closing, 15920.0)

    def test_closing_rate_raises_if_no_data(self):
        """UserError jika tidak ada kurs sebelum tanggal closing."""
        config = self._make_config('2005-01-01', '2005-12-31')
        engine = self.env['acc.id.translation.engine']
        with self.assertRaises(UserError):
            engine._compute_closing_rate(config)

    # ── Test: Full Calculation ────────────────────────────────────────────────

    def test_full_calculation_creates_report_lines(self):
        """Setelah kalkulasi, report lines terbentuk dan state = calculated."""
        config = self._make_config()
        config.action_calculate()

        self.assertEqual(config.state, 'calculated')
        self.assertGreater(len(config.report_line_ids), 0,
            'Harus ada minimal 1 report line setelah kalkulasi')

    def test_full_calculation_creates_immutable_log(self):
        """Setelah kalkulasi, calc log terbentuk dan tidak bisa dihapus."""
        config = self._make_config()
        config.action_calculate()

        self.assertEqual(len(config.calc_log_ids), 1)
        log = config.calc_log_ids[0]
        self.assertEqual(log.result, 'success')

        with self.assertRaises(UserError,
             msg='Log kalkulasi harus immutable — unlink harus raise UserError'):
            log.unlink()

    def test_calc_log_cannot_be_written(self):
        """Log tidak bisa di-edit setelah dibuat."""
        config = self._make_config()
        config.action_calculate()
        log = config.calc_log_ids[0]

        with self.assertRaises(UserError,
             msg='Log kalkulasi harus immutable — write harus raise UserError'):
            log.write({'notes': 'Coba ubah'})

    def test_conversion_idr_to_usd(self):
        """
        Verifikasi konversi: revenue IDR 100.000.000
        dengan avg rate ≈ 15867 harus menghasilkan ekuivalen USD yang benar.
        """
        config = self._make_config()
        config.action_calculate()

        revenue_line = config.report_line_ids.filtered(
            lambda l: l.account_id.id == self.account_revenue.id
        )
        self.assertTrue(revenue_line,
            'Harus ada report line untuk akun revenue test')

        expected_avg = (15550 + 15720 + 16043 + 15920 + 16102) / 5
        expected_usd = -100_000_000.0 / expected_avg  # credit = negatif

        self.assertAlmostEqual(
            revenue_line.balance_presentation,
            expected_usd,
            places=0,
            msg='Konversi IDR → USD harus menggunakan average rate',
        )

    def test_recalculate_replaces_old_lines(self):
        """Hitung ulang menghapus lines lama dan membuat yang baru."""
        config = self._make_config()
        config.action_calculate()
        first_count = len(config.report_line_ids)

        config.action_calculate()
        second_count = len(config.report_line_ids)

        self.assertEqual(first_count, second_count,
            'Jumlah lines harus sama setelah hitung ulang')
        self.assertEqual(len(config.calc_log_ids), 2,
            'Harus ada 2 entri log setelah 2x kalkulasi')

    # ── Test: Rate Override ───────────────────────────────────────────────────

    def test_rate_override_per_account(self):
        """Override kurs manual per akun diterapkan dalam kalkulasi."""
        config = self._make_config()
        self.env['acc.id.fx.rate.override'].create({
            'config_id': config.id,
            'account_id': self.account_revenue.id,
            'rate_type_override': 'manual',
            'manual_rate': 15000.0,
            'reason': 'Test override untuk unit test',
        })

        config.action_calculate()

        revenue_line = config.report_line_ids.filtered(
            lambda l: l.account_id.id == self.account_revenue.id
        )
        self.assertTrue(revenue_line.is_override,
            'Baris dengan override harus memiliki is_override = True')
        self.assertEqual(revenue_line.rate_used, 15000.0,
            'Kurs yang dipakai harus sesuai override manual')
        expected_usd = -100_000_000.0 / 15000.0
        self.assertAlmostEqual(
            revenue_line.balance_presentation, expected_usd, places=0
        )

    # ── Test: Account Effective Rate Type ─────────────────────────────────────

    def test_income_account_defaults_to_average(self):
        """Akun income tanpa override harus default ke average rate."""
        rate_type = self.account_revenue._get_effective_fx_rate_type()
        self.assertEqual(rate_type, 'average')

    def test_expense_account_defaults_to_average(self):
        """Akun expense tanpa override harus default ke average rate."""
        rate_type = self.account_expense._get_effective_fx_rate_type()
        self.assertEqual(rate_type, 'average')

    def test_cash_account_defaults_to_closing(self):
        """Akun asset_cash tanpa override harus default ke closing rate."""
        rate_type = self.account_cash._get_effective_fx_rate_type()
        self.assertEqual(rate_type, 'closing')

    def test_explicit_rate_type_overrides_default(self):
        """Jika id_fx_rate_type diisi eksplisit, gunakan itu."""
        self.account_revenue.id_fx_rate_type = 'closing'
        rate_type = self.account_revenue._get_effective_fx_rate_type()
        self.assertEqual(rate_type, 'closing')
        # Reset
        self.account_revenue.id_fx_rate_type = False

    # ── Test: Validation ──────────────────────────────────────────────────────

    def test_config_validation_date_order(self):
        """date_from > date_to harus raise ValidationError."""
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.env['acc.id.fx.report.config'].create({
                'name': 'Invalid Date Test',
                'company_id': self.company.id,
                'report_currency_id': self.usd.id,
                'pl_date_from': '2024-12-31',
                'pl_date_to': '2024-01-01',
                'bs_closing_date': '2024-01-01',
                'scenario': 'idr_functional',
            })

    def test_config_validation_same_currency(self):
        """Functional = presentation currency harus raise ValidationError."""
        from odoo.exceptions import ValidationError
        idr = self.company.currency_id
        with self.assertRaises(ValidationError):
            self.env['acc.id.fx.report.config'].create({
                'name': 'Same Currency Test',
                'company_id': self.company.id,
                'report_currency_id': idr.id,
                'pl_date_from': '2024-01-01',
                'pl_date_to': '2024-12-31',
                'bs_closing_date': '2024-12-31',
                'scenario': 'idr_functional',
            })
