# -*- coding: utf-8 -*-
import math
import logging

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class FxDrilldownController(http.Controller):

    @http.route(
        '/acc_id_fx/drilldown',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True,
    )
    def get_drilldown(
        self, config_id, account_id,
        page=1, page_size=50, **kwargs
    ):
        """
        Lazy-load endpoint untuk drill-down transaksi per akun.
        Dipanggil via AJAX dari laporan HTML.

        Return: dict dengan transactions, pagination, dan totals akun.
        """
        try:
            page = max(1, int(page))
            page_size = min(100, max(25, int(page_size)))

            config = request.env['acc.id.fx.report.config'].browse(
                int(config_id)
            )
            if not config.exists():
                return {'error': _('Config laporan tidak ditemukan.')}

            config.check_access_rights('read')
            config.check_access_rule('read')

            account = request.env['account.account'].browse(int(account_id))
            if not account.exists():
                return {'error': _('Akun tidak ditemukan.')}

            # Cari report line untuk akun ini
            report_line = config.report_line_ids.filtered(
                lambda l: l.account_id.id == account.id
            )
            if not report_line:
                return {
                    'error': _(
                        'Baris laporan tidak ditemukan untuk akun %s.'
                    ) % account.code
                }
            report_line = report_line[0]

            # Tentukan filter tanggal berdasarkan report_type
            if report_line.report_type == 'pl':
                date_from = config.pl_date_from
                date_to = config.pl_date_to
            else:
                date_from = None  # BS: dari awal waktu
                date_to = config.bs_closing_date

            # Hitung total untuk pagination
            total_count = _count_transactions(
                request.env.cr,
                config.company_id.id,
                account.id,
                date_from,
                date_to,
            )

            # Fetch dengan pagination
            offset = (page - 1) * page_size
            transactions = _fetch_transactions(
                request.env.cr,
                config.company_id.id,
                account.id,
                date_from,
                date_to,
                limit=page_size,
                offset=offset,
            )

            total_pages = (
                math.ceil(total_count / page_size) if total_count > 0 else 1
            )

            return {
                'account_id': account.id,
                'account_code': account.code,
                'account_name': account.name,
                'config_id': config.id,
                'report_type': report_line.report_type,
                'rate_used': report_line.rate_used,
                'rate_type': report_line.rate_type_applied,
                'balance_idr': report_line.balance_functional,
                'balance_usd': report_line.balance_presentation,
                'is_override': report_line.is_override,
                'override_reason': report_line.override_reason or '',
                'transactions': transactions,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': total_pages,
                    'has_prev': page > 1,
                    'has_next': page < total_pages,
                },
            }

        except Exception as exc:
            _logger.exception(
                'FX Drilldown error: config=%s account=%s',
                config_id, account_id
            )
            return {'error': str(exc)}

    @http.route(
        '/acc_id_fx/pl_report/<int:config_id>',
        type='http',
        auth='user',
        website=False,
    )
    def pl_report(self, config_id, **kwargs):
        """Render laporan Laba Rugi sebagai HTML."""
        config = request.env['acc.id.fx.report.config'].browse(config_id)
        if not config.exists():
            return request.not_found()

        config.check_access_rights('read')
        config.check_access_rule('read')

        # Re-check stale saat laporan dibuka
        is_stale = config.check_and_update_stale()

        pl_lines = config.report_line_ids.filtered(
            lambda l: l.report_type == 'pl'
        ).sorted('account_code')

        grouped = _group_pl_lines(pl_lines)

        return request.render(
            'acc_id_multicurrency_report.fx_pl_report_template',
            {
                'config': config,
                'grouped': grouped,
                'is_stale': is_stale,
                'company': config.company_id,
                'functional_symbol': (
                    config.functional_currency_id.symbol or 'Rp'
                ),
                'presentation_symbol': (
                    config.report_currency_id.symbol or '$'
                ),
            }
        )

    @http.route(
        '/acc_id_fx/bs_report/<int:config_id>',
        type='http',
        auth='user',
        website=False,
    )
    def bs_report(self, config_id, **kwargs):
        """Render laporan Neraca sebagai HTML."""
        config = request.env['acc.id.fx.report.config'].browse(config_id)
        if not config.exists():
            return request.not_found()

        config.check_access_rights('read')
        config.check_access_rule('read')

        is_stale = config.check_and_update_stale()

        bs_lines = config.report_line_ids.filtered(
            lambda l: l.report_type == 'bs'
        ).sorted('account_code')

        grouped = _group_bs_lines(bs_lines)

        return request.render(
            'acc_id_multicurrency_report.fx_bs_report_template',
            {
                'config': config,
                'grouped': grouped,
                'is_stale': is_stale,
                'company': config.company_id,
                'functional_symbol': (
                    config.functional_currency_id.symbol or 'Rp'
                ),
                'presentation_symbol': (
                    config.report_currency_id.symbol or '$'
                ),
            }
        )


# ── Helper functions ──────────────────────────────────────────────────────────

def _count_transactions(cr, company_id, account_id, date_from, date_to):
    if date_from:
        cr.execute("""
            SELECT COUNT(*)
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            WHERE am.state      = 'posted'
              AND am.company_id = %s
              AND aml.account_id= %s
              AND aml.date     >= %s
              AND aml.date     <= %s
        """, (company_id, account_id, date_from, date_to))
    else:
        cr.execute("""
            SELECT COUNT(*)
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            WHERE am.state      = 'posted'
              AND am.company_id = %s
              AND aml.account_id= %s
              AND aml.date     <= %s
        """, (company_id, account_id, date_to))
    return cr.fetchone()[0]


def _fetch_transactions(
    cr, company_id, account_id, date_from, date_to, limit, offset
):
    base_sql = """
        SELECT
            aml.id,
            aml.date,
            am.name          AS move_name,
            am.ref           AS move_ref,
            rp.name          AS partner_name,
            aml.name         AS label,
            aml.debit,
            aml.credit,
            aml.balance,
            aml.amount_currency,
            rc.name          AS currency_name
        FROM account_move_line aml
        JOIN account_move  am  ON am.id  = aml.move_id
        LEFT JOIN res_partner   rp  ON rp.id  = aml.partner_id
        LEFT JOIN res_currency  rc  ON rc.id  = aml.currency_id
        WHERE am.state      = 'posted'
          AND am.company_id = %s
          AND aml.account_id= %s
    """
    if date_from:
        cr.execute(
            base_sql + """
              AND aml.date >= %s
              AND aml.date <= %s
            ORDER BY aml.date DESC, aml.id DESC
            LIMIT %s OFFSET %s
            """,
            (company_id, account_id, date_from, date_to, limit, offset),
        )
    else:
        cr.execute(
            base_sql + """
              AND aml.date <= %s
            ORDER BY aml.date DESC, aml.id DESC
            LIMIT %s OFFSET %s
            """,
            (company_id, account_id, date_to, limit, offset),
        )

    rows = cr.dictfetchall()
    for row in rows:
        if row.get('date'):
            row['date'] = row['date'].strftime('%d %b %Y')
        row['debit'] = float(row['debit'] or 0)
        row['credit'] = float(row['credit'] or 0)
        row['balance'] = float(row['balance'] or 0)
        row['amount_currency'] = float(row['amount_currency'] or 0)
    return rows


def _group_pl_lines(lines):
    _INCOME = frozenset({'income', 'income_other'})
    _EXPENSE = frozenset({
        'expense', 'expense_depreciation', 'expense_direct_cost'
    })

    income = lines.filtered(lambda l: l.account_type in _INCOME)
    expense = lines.filtered(lambda l: l.account_type in _EXPENSE)
    other = lines.filtered(
        lambda l: l.account_type not in _INCOME | _EXPENSE
    )

    ti_idr = sum(income.mapped('balance_functional'))
    ti_usd = sum(income.mapped('balance_presentation'))
    te_idr = sum(expense.mapped('balance_functional'))
    te_usd = sum(expense.mapped('balance_presentation'))

    return {
        'income_lines': income,
        'expense_lines': expense,
        'other_lines': other,
        'total_income_idr': ti_idr,
        'total_income_usd': ti_usd,
        'total_expense_idr': te_idr,
        'total_expense_usd': te_usd,
        'net_idr': ti_idr + te_idr,
        'net_usd': ti_usd + te_usd,
    }


def _group_bs_lines(lines):
    _ASSET = frozenset({
        'asset_cash', 'asset_receivable', 'asset_current',
        'asset_non_current', 'asset_prepayments', 'asset_fixed',
    })
    _LIABILITY = frozenset({
        'liability_payable', 'liability_current', 'liability_non_current',
    })
    _EQUITY = frozenset({'equity', 'equity_unaffected'})

    assets = lines.filtered(lambda l: l.account_type in _ASSET)
    liabilities = lines.filtered(lambda l: l.account_type in _LIABILITY)
    equity = lines.filtered(lambda l: l.account_type in _EQUITY)

    ta_idr = sum(assets.mapped('balance_functional'))
    ta_usd = sum(assets.mapped('balance_presentation'))
    tl_idr = sum(liabilities.mapped('balance_functional'))
    tl_usd = sum(liabilities.mapped('balance_presentation'))
    te_idr = sum(equity.mapped('balance_functional'))
    te_usd = sum(equity.mapped('balance_presentation'))

    tle_idr = tl_idr + te_idr
    tle_usd = tl_usd + te_usd

    return {
        'asset_lines': assets,
        'liability_lines': liabilities,
        'equity_lines': equity,
        'total_asset_idr': ta_idr,
        'total_asset_usd': ta_usd,
        'total_liability_idr': tl_idr,
        'total_liability_usd': tl_usd,
        'total_equity_idr': te_idr,
        'total_equity_usd': te_usd,
        'total_liab_equity_idr': tle_idr,
        'total_liab_equity_usd': tle_usd,
        'diff_idr': abs(ta_idr - tle_idr),
        'diff_usd': abs(ta_usd - tle_usd),
        'is_balanced': abs(ta_idr - tle_idr) < 1.0,
    }
