# -*- coding: utf-8 -*-
import logging

from . import models
from . import wizard
from . import report
from . import controllers

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    Dijalankan sekali saat pertama install.
    Tidak mengubah id_fx_rate_type yang sudah ada —
    default logic ada di _get_effective_fx_rate_type() di account.account.
    Fungsi ini hanya melakukan logging informasi instalasi.
    """
    account_count = env['account.account'].search_count([
        ('company_ids', 'in', env['res.company'].search([]).ids),
    ])
    _logger.info(
        'acc_id_multicurrency_report: post_init_hook selesai. '
        '%d akun tersedia. Default rate type akan ditentukan secara '
        'otomatis berdasarkan account_type via _get_effective_fx_rate_type().',
        account_count,
    )
