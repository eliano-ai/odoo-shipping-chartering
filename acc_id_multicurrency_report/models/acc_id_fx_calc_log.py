# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class AccIdFxCalcLog(models.Model):
    _name = 'acc.id.fx.calc.log'
    _description = 'Log Kalkulasi Laporan Dual-Currency'
    _order = 'run_at desc'
    _rec_name = 'run_at'

    config_id = fields.Many2one(
        comodel_name='acc.id.fx.report.config',
        string='Config Laporan',
        required=True,
        ondelete='restrict',
        index=True,
    )

    run_at = fields.Datetime(
        string='Waktu Kalkulasi',
        required=True,
        default=fields.Datetime.now,
        readonly=True,
    )

    run_by = fields.Many2one(
        comodel_name='res.users',
        string='Dijalankan Oleh',
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
    )

    pl_avg_rate_used = fields.Float(
        string='Kurs Rata-rata P&L',
        digits=(16, 4),
        readonly=True,
    )

    bs_closing_rate_used = fields.Float(
        string='Kurs Closing Neraca',
        digits=(16, 4),
        readonly=True,
    )

    rate_source = fields.Char(
        string='Sumber Kurs',
        readonly=True,
    )

    lines_computed = fields.Integer(
        string='Jumlah Baris Dihitung',
        readonly=True,
    )

    duration_seconds = fields.Float(
        string='Durasi (detik)',
        digits=(10, 2),
        readonly=True,
    )

    trigger_reason = fields.Selection(
        selection=[
            ('manual', 'Manual oleh User'),
            ('rate_change', 'Perubahan Kurs'),
            ('transaction_change', 'Perubahan Transaksi'),
        ],
        string='Alasan Trigger',
        default='manual',
        readonly=True,
    )

    result = fields.Selection(
        selection=[
            ('success', 'Berhasil'),
            ('error', 'Error'),
        ],
        string='Hasil',
        default='success',
        readonly=True,
    )

    error_message = fields.Text(
        string='Pesan Error',
        readonly=True,
    )

    notes = fields.Text(
        string='Catatan',
        readonly=True,
    )

    # ── Immutability enforcement ──────────────────────────────────────────────

    def unlink(self):
        """
        Log kalkulasi tidak bisa dihapus kecuali oleh group FX Admin.
        Ini adalah safeguard utama audit trail modul ini.
        """
        if not self.env.user.has_group(
            'acc_id_multicurrency_report.group_fx_admin'
        ):
            raise UserError(_(
                'Log kalkulasi tidak dapat dihapus untuk menjaga '
                'integritas audit trail.\n\n'
                'Hubungi administrator sistem jika ada kebutuhan khusus.'
            ))
        return super().unlink()

    def write(self, vals):
        """Log tidak bisa diubah setelah dibuat — immutable by design."""
        raise UserError(_(
            'Log kalkulasi tidak dapat diubah setelah dibuat. '
            'Ini adalah catatan audit yang immutable.'
        ))
