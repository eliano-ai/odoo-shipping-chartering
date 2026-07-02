# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install', 'fx_report', 'fx_config')
class TestReportConfig(TransactionCase):
    """
    Unit test untuk acc.id.fx.report.config — state machine dan stale detection.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref('base.main_company')
        cls.usd = cls.env.ref('base.USD')
        cls.usd.active = True

        # Kurs minimal untuk test
        cls.env['res.currency.rate'].search([
            ('currency_id', '=', cls.usd.id),
            ('name', '=', '2024-12-31'),
            ('company_id', '=', cls.company.id),
        ]).unlink()
        cls.env['res.currency.rate'].create({
            'currency_id': cls.usd.id,
            'name': '2024-12-31',
            'rate': 16102.0,
            'rate_source': 'manual',
            'company_id': cls.company.id,
        })

    def _make_config(self):
        return self.env['acc.id.fx.report.config'].create({
            'name': 'Test Config State',
            'company_id': self.company.id,
            'report_currency_id': self.usd.id,
            'pl_date_from': '2024-01-01',
            'pl_date_to': '2024-12-31',
            'bs_closing_date': '2024-12-31',
            'rate_source': 'manual',
            'scenario': 'idr_functional',
        })

    def test_initial_state_is_draft(self):
        config = self._make_config()
        self.assertEqual(config.state, 'draft')

    def test_state_becomes_calculated_after_calculate(self):
        config = self._make_config()
        config.action_calculate()
        self.assertEqual(config.state, 'calculated')

    def test_manual_rate_change_triggers_stale(self):
        """
        Mengubah kurs secara manual setelah state = calculated
        harus otomatis set state ke stale.
        """
        config = self._make_config()
        config.action_calculate()
        self.assertEqual(config.state, 'calculated')

        config.write({'pl_avg_rate': 17000.0})
        self.assertEqual(config.state, 'stale',
            'State harus berubah ke stale jika kurs diubah manual')

    def test_open_report_before_calculate_raises(self):
        """Membuka laporan sebelum dihitung harus raise UserError."""
        config = self._make_config()
        with self.assertRaises(UserError):
            config.action_open_pl_report()
        with self.assertRaises(UserError):
            config.action_open_bs_report()

    def test_rate_override_unique_per_config(self):
        """Tidak boleh ada dua override untuk akun yang sama dalam satu config."""
        from odoo.exceptions import ValidationError
        config = self._make_config()
        account = self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_id', '=', self.company.id),
        ], limit=1)
        if not account:
            return  # Skip jika tidak ada akun

        self.env['acc.id.fx.rate.override'].create({
            'config_id': config.id,
            'account_id': account.id,
            'rate_type_override': 'closing',
            'reason': 'Test pertama',
        })
        with self.assertRaises(ValidationError):
            self.env['acc.id.fx.rate.override'].create({
                'config_id': config.id,
                'account_id': account.id,
                'rate_type_override': 'average',
                'reason': 'Test duplikat',
            })

    def test_manual_rate_override_requires_value(self):
        """Override tipe manual tanpa nilai kurs harus raise ValidationError."""
        from odoo.exceptions import ValidationError
        config = self._make_config()
        account = self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_id', '=', self.company.id),
        ], limit=1)
        if not account:
            return

        with self.assertRaises(ValidationError):
            self.env['acc.id.fx.rate.override'].create({
                'config_id': config.id,
                'account_id': account.id,
                'rate_type_override': 'manual',
                'manual_rate': 0.0,  # Invalid — harus > 0
                'reason': 'Test manual tanpa nilai',
            })
