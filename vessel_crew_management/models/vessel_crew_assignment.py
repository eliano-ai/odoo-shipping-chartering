from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, timedelta
import logging
import re

_logger = logging.getLogger(__name__)

SIGN_OFF_REASON = [
    ('end_of_contract', 'Selesai Kontrak'),
    ('medical', 'Alasan Medis'),
    ('personal', 'Alasan Pribadi'),
    ('emergency', 'Keadaan Darurat'),
    ('termination', 'Pemutusan Hubungan Kerja'),
    ('repatriation', 'Repatriasi'),
    ('other', 'Lainnya'),
]

ASSIGNMENT_STATE = [
    ('draft', 'Draft'),
    ('confirmed', 'Confirmed'),
    ('on_board', 'On Board'),
    ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
]

NOTIFICATION_CHANNEL = [
    ('email', 'Email'),
    ('whatsapp', 'WhatsApp'),
    ('both', 'Email & WhatsApp'),
]


class VesselCrewAssignment(models.Model):
    _name = 'vessel.crew.assignment'
    _description = 'Penugasan ABK — Sign On / Sign Off'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sign_on_date desc, vehicle_id'
    _rec_name = 'display_name'

    # ── Identitas Penugasan ────────────────────────────────────────────────
    display_name = fields.Char(
        compute='_compute_display_name', store=True,
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Kapal',
        required=True, tracking=True,
        domain=[('is_vessel', '=', True)],
        index=True,
    )
    seafarer_id = fields.Many2one(
        'vessel.seafarer', string='ABK',
        required=True, tracking=True,
        index=True,
    )
    rank_id = fields.Many2one(
        'vessel.crew.rank', string='Jabatan dalam Penugasan Ini',
        required=True, tracking=True,
        help='Jabatan ABK dalam penugasan ini (bisa berbeda dari rank default-nya).',
    )

    # ── Jadwal Penugasan ───────────────────────────────────────────────────
    sign_on_date = fields.Date(
        string='Tanggal Sign On (Rencana)', required=True, tracking=True,
    )
    sign_on_port = fields.Char(
        string='Pelabuhan Sign On', tracking=True,
    )
    sign_on_actual_date = fields.Date(
        string='Tanggal Sign On (Aktual)',
        help='Diisi saat ABK benar-benar naik kapal.',
        tracking=True,
    )
    sign_off_date = fields.Date(
        string='Tanggal Sign Off (Rencana)', tracking=True,
    )
    sign_off_port = fields.Char(
        string='Pelabuhan Sign Off', tracking=True,
    )
    sign_off_actual_date = fields.Date(
        string='Tanggal Sign Off (Aktual)',
        tracking=True,
    )
    sign_off_reason = fields.Selection(
        SIGN_OFF_REASON, string='Alasan Sign Off',
        tracking=True,
    )
    contract_duration_days = fields.Integer(
        string='Durasi Kontrak (hari)',
        compute='_compute_durations', store=True,
    )
    sea_service_days = fields.Integer(
        string='Hari di Laut (Aktual)',
        compute='_compute_durations', store=True,
        help='Dihitung dari sign_on_actual_date ke sign_off_actual_date.',
    )

    # ── State machine ──────────────────────────────────────────────────────
    state = fields.Selection(
        ASSIGNMENT_STATE, string='Status',
        default='draft', tracking=True, index=True,
    )

    # ── Validasi Sertifikat ────────────────────────────────────────────────
    cert_validated = fields.Boolean(
        string='Sertifikat Sudah Divalidasi',
        default=False, tracking=True,
    )
    cert_validation_date = fields.Datetime(
        string='Waktu Validasi Cert',
    )
    cert_validation_notes = fields.Text(
        string='Catatan Validasi Cert',
        help='Daftar cert yang bermasalah saat validasi.',
    )
    has_cert_warning = fields.Boolean(
        string='Ada Peringatan Cert',
        compute='_compute_cert_warnings', store=True,
    )
    cert_warning_details = fields.Text(
        compute='_compute_cert_warnings', store=True,
        string='Detail Peringatan Cert',
    )

    # ── Notifikasi ─────────────────────────────────────────────────────────
    notification_channel = fields.Selection(
        NOTIFICATION_CHANNEL, string='Kanal Notifikasi',
        default='both', required=True,
    )
    notification_sent = fields.Boolean(
        string='Notifikasi Terkirim', default=False, tracking=True,
    )
    notification_sent_date = fields.Datetime(
        string='Waktu Notifikasi Terkirim',
    )
    reminder_sent = fields.Boolean(
        string='Reminder H-3 Terkirim', default=False,
    )
    notification_log_ids = fields.One2many(
        'vessel.notification.log', 'assignment_id',
        string='Log Notifikasi',
    )

    # ── Sea Service Log ────────────────────────────────────────────────────
    sea_service_log_ids = fields.One2many(
        'vessel.sea.service.log', 'assignment_id',
        string='Sea Service Log',
    )

    # ── Meta ───────────────────────────────────────────────────────────────
    notes = fields.Text(string='Catatan')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True,
    )

    # ─────────────────────────────────────────────────────────────────────
    # Compute
    # ─────────────────────────────────────────────────────────────────────

    @api.depends('seafarer_id', 'vehicle_id', 'sign_on_date', 'rank_id')
    def _compute_display_name(self):
        for rec in self:
            parts = [
                rec.seafarer_id.name or '',
                rec.vehicle_id.name or '',
                str(rec.sign_on_date) if rec.sign_on_date else '',
            ]
            rec.display_name = ' · '.join(filter(None, parts))

    @api.depends('sign_on_date', 'sign_off_date',
                 'sign_on_actual_date', 'sign_off_actual_date')
    def _compute_durations(self):
        for rec in self:
            if rec.sign_on_date and rec.sign_off_date:
                rec.contract_duration_days = (
                    rec.sign_off_date - rec.sign_on_date
                ).days
            else:
                rec.contract_duration_days = 0

            if rec.sign_on_actual_date and rec.sign_off_actual_date:
                rec.sea_service_days = (
                    rec.sign_off_actual_date - rec.sign_on_actual_date
                ).days
            elif rec.sign_on_actual_date and rec.state == 'on_board':
                rec.sea_service_days = (date.today() - rec.sign_on_actual_date).days
            else:
                rec.sea_service_days = 0

    @api.depends('seafarer_id', 'sign_on_date', 'sign_off_date',
                 'seafarer_id.cert_document_ids',
                 'seafarer_id.cert_document_ids.state',
                 'seafarer_id.cert_document_ids.expiry_date')
    def _compute_cert_warnings(self):
        for rec in self:
            if not rec.seafarer_id or not rec.sign_on_date:
                rec.has_cert_warning = False
                rec.cert_warning_details = ''
                continue

            warnings = []
            sign_off = rec.sign_off_date or (
                rec.sign_on_date + timedelta(days=rec.contract_duration_days or 90)
            )

            for cert in rec.seafarer_id.cert_document_ids:
                if cert.state == 'expired':
                    warnings.append(
                        f"EXPIRED: {cert.doc_type_id.name or cert.doc_type}"
                        f" (expired {cert.expiry_date})"
                    )
                elif cert.state == 'expiring_soon':
                    if cert.expiry_date and cert.expiry_date < sign_off:
                        warnings.append(
                            f"AKAN EXPIRED saat bertugas: "
                            f"{cert.doc_type_id.name or cert.doc_type}"
                            f" — {cert.expiry_date} ({cert.days_remaining} hari lagi)"
                        )

            rec.has_cert_warning = bool(warnings)
            rec.cert_warning_details = '\n'.join(warnings)

    # ─────────────────────────────────────────────────────────────────────
    # Constraints
    # ─────────────────────────────────────────────────────────────────────

    @api.constrains('sign_on_date', 'sign_off_date')
    def _check_dates(self):
        for rec in self:
            if rec.sign_on_date and rec.sign_off_date:
                if rec.sign_off_date <= rec.sign_on_date:
                    raise ValidationError(_(
                        "Tanggal sign off harus setelah tanggal sign on."
                    ))

    @api.constrains('seafarer_id', 'state', 'vehicle_id')
    def _check_no_double_assignment(self):
        for rec in self:
            if rec.state in ('confirmed', 'on_board'):
                conflict = self.search([
                    ('seafarer_id', '=', rec.seafarer_id.id),
                    ('state', 'in', ('confirmed', 'on_board')),
                    ('id', '!=', rec.id),
                ])
                if conflict:
                    raise ValidationError(_(
                        "ABK %s sudah memiliki penugasan aktif di %s.\n"
                        "Selesaikan atau batalkan penugasan tersebut terlebih dahulu."
                    ) % (rec.seafarer_id.display_name, conflict[0].vehicle_id.name))

    # ─────────────────────────────────────────────────────────────────────
    # State machine actions
    # ─────────────────────────────────────────────────────────────────────

    def action_confirm(self):
        """Confirm assignment: validate certs, send notification to crew."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Hanya assignment dengan status Draft yang bisa dikonfirmasi."))

            # Validasi sertifikat
            rec._validate_certs()

            # Kirim notifikasi ke ABK
            rec._send_schedule_notification()

            # Update status ABK di manning pool
            rec.seafarer_id.write({'manning_pool_status': 'standby'})

            rec.write({'state': 'confirmed'})
            rec.message_post(
                body=_("Assignment dikonfirmasi. Notifikasi jadwal telah dikirim ke %s.")
                     % rec.seafarer_id.display_name,
            )

    def action_sign_on(self):
        """Record actual sign on — ABK boards the vessel."""
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(_("Hanya assignment Confirmed yang bisa di-sign on."))

            actual_date = rec.sign_on_actual_date or date.today()
            rec.write({
                'state': 'on_board',
                'sign_on_actual_date': actual_date,
            })

            # Update status ABK
            rec.seafarer_id.write({'manning_pool_status': 'on_board'})

            # Kirim notifikasi sign on
            rec._send_sign_on_notification()

            rec.message_post(
                body=_("ABK %s telah sign on di %s pada %s di %s.")
                     % (rec.seafarer_id.display_name, rec.vehicle_id.name,
                        actual_date, rec.sign_on_port or '-'),
            )

    def action_sign_off(self):
        """Open sign off wizard."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sign Off — %s') % self.display_name,
            'res_model': 'vessel.sign.off.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_assignment_id': self.id},
        }

    def _do_sign_off(self, sign_off_date, sign_off_port, reason, notes=''):
        """Called by wizard to complete sign off."""
        self.ensure_one()
        if self.state != 'on_board':
            raise UserError(_("Hanya assignment On Board yang bisa di-sign off."))

        self.write({
            'state': 'completed',
            'sign_off_actual_date': sign_off_date,
            'sign_off_port': sign_off_port,
            'sign_off_reason': reason,
            'notes': (self.notes or '') + ('\n' + notes if notes else ''),
        })

        # Buat sea service log
        self._create_sea_service_log(sign_off_date)

        # Update status ABK kembali ke available
        self.seafarer_id.write({'manning_pool_status': 'available'})

        # Kirim notifikasi sign off
        self._send_sign_off_notification()

        self.message_post(
            body=_("ABK %s telah sign off dari %s pada %s di %s. Alasan: %s. Total %d hari.")
                 % (self.seafarer_id.display_name, self.vehicle_id.name,
                    sign_off_date, sign_off_port,
                    dict(SIGN_OFF_REASON).get(reason, reason),
                    self.sea_service_days),
        )

    def action_cancel(self):
        """Cancel a draft or confirmed assignment."""
        for rec in self:
            if rec.state == 'on_board':
                raise UserError(_(
                    "Tidak bisa membatalkan assignment yang sedang On Board. "
                    "Lakukan sign off terlebih dahulu."
                ))
            if rec.state == 'completed':
                raise UserError(_("Assignment yang sudah Completed tidak bisa dibatalkan."))

            if rec.seafarer_id.manning_pool_status == 'standby':
                rec.seafarer_id.write({'manning_pool_status': 'available'})

            rec.write({'state': 'cancelled'})
            rec.message_post(body=_("Assignment dibatalkan."))

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state not in ('cancelled',):
                raise UserError(_("Hanya assignment Cancelled yang bisa dikembalikan ke Draft."))
            rec.write({'state': 'draft', 'notification_sent': False})

    def action_view_sea_service(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sea Service Log — %s') % self.display_name,
            'res_model': 'vessel.sea.service.log',
            'view_mode': 'list,form',
            'domain': [('assignment_id', '=', self.id)],
            'context': {'default_assignment_id': self.id},
        }

    # ─────────────────────────────────────────────────────────────────────
    # Cert validation
    # ─────────────────────────────────────────────────────────────────────

    def _validate_certs(self):
        """Check required certs. Block if expired, warn if expiring during voyage."""
        self.ensure_one()
        seafarer = self.seafarer_id
        expired_certs = [
            c for c in seafarer.cert_document_ids
            if c.state == 'expired'
        ]

        if expired_certs:
            cert_list = '\n'.join(
                f"  - {c.doc_type_id.name or c.doc_type} (expired: {c.expiry_date})"
                for c in expired_certs
            )
            raise ValidationError(_(
                "Tidak dapat mengkonfirmasi penugasan.\n\n"
                "ABK %s memiliki sertifikat yang sudah EXPIRED:\n%s\n\n"
                "Perbarui sertifikat sebelum melanjutkan."
            ) % (seafarer.display_name, cert_list))

        now = fields.Datetime.now()
        self.write({
            'cert_validated': True,
            'cert_validation_date': now,
            'cert_validation_notes': self.cert_warning_details or 'Semua sertifikat valid.',
        })

    # ─────────────────────────────────────────────────────────────────────
    # Sea service log
    # ─────────────────────────────────────────────────────────────────────

    def _create_sea_service_log(self, sign_off_date):
        self.ensure_one()
        vessel = self.vehicle_id
        self.env['vessel.sea.service.log'].create({
            'assignment_id': self.id,
            'seafarer_id': self.seafarer_id.id,
            'vehicle_id': vessel.id,
            'rank_id': self.rank_id.id,
            'from_date': self.sign_on_actual_date,
            'to_date': sign_off_date,
            'sign_on_port': self.sign_on_port or '',
            'sign_off_port': self.sign_off_port or '',
            'vessel_name': vessel.name,
            'vessel_gt': str(vessel.gross_tonnage or ''),
            'vessel_flag': vessel.flag_state or 'Indonesia',
        })

    # ─────────────────────────────────────────────────────────────────────
    # Notification engine
    # ─────────────────────────────────────────────────────────────────────

    def _get_notification_context(self):
        """Build template context dict for notifications."""
        self.ensure_one()
        return {
            'seafarer_name': self.seafarer_id.name,
            'vessel_name': self.vehicle_id.name,
            'rank_name': self.rank_id.name,
            'sign_on_date': self.sign_on_date.strftime('%d %B %Y') if self.sign_on_date else '-',
            'sign_on_port': self.sign_on_port or '-',
            'sign_off_date': self.sign_off_date.strftime('%d %B %Y') if self.sign_off_date else '-',
            'cert_warnings': self.cert_warning_details or '',
            'company_name': self.company_id.name,
        }

    def _send_schedule_notification(self):
        """Send sign-on schedule notification via email and/or WhatsApp."""
        self.ensure_one()
        channel = self.notification_channel
        seafarer = self.seafarer_id
        ctx = self._get_notification_context()
        sent_channels = []

        if channel in ('email', 'both'):
            email = seafarer.work_email or seafarer.employee_id.work_email
            if email:
                template = self.env.ref(
                    'vessel_crew_management.email_template_crew_schedule',
                    raise_if_not_found=False,
                )
                if template:
                    template.with_context(**ctx).send_mail(self.id, force_send=True)
                    sent_channels.append('email')
                    self._log_notification('schedule', 'email', 'sent')
                else:
                    self._send_schedule_email_fallback(email, ctx)
                    sent_channels.append('email')
                    self._log_notification('schedule', 'email', 'sent')
            else:
                _logger.warning(
                    "Vessel crew assignment %s: seafarer %s tidak memiliki email.",
                    self.id, seafarer.display_name,
                )
                self._log_notification('schedule', 'email', 'failed',
                                       'Email ABK tidak ditemukan')

        if channel in ('whatsapp', 'both'):
            wa_number = self._clean_wa_number(seafarer.whatsapp_number)
            if wa_number:
                self._send_whatsapp(wa_number, self._build_schedule_wa_message(ctx))
                sent_channels.append('whatsapp')
                self._log_notification('schedule', 'whatsapp', 'sent')
            else:
                _logger.warning(
                    "Vessel crew assignment %s: seafarer %s tidak memiliki WA number.",
                    self.id, seafarer.display_name,
                )
                self._log_notification('schedule', 'whatsapp', 'failed',
                                       'Nomor WhatsApp ABK tidak ditemukan')

        if sent_channels:
            self.write({
                'notification_sent': True,
                'notification_sent_date': fields.Datetime.now(),
            })

    def _send_reminder_notification(self):
        """H-3 reminder — called by cron."""
        self.ensure_one()
        if self.reminder_sent:
            return
        ctx = self._get_notification_context()
        channel = self.notification_channel
        seafarer = self.seafarer_id

        if channel in ('email', 'both'):
            email = seafarer.work_email or seafarer.employee_id.work_email
            if email:
                self._send_reminder_email_fallback(email, ctx)
                self._log_notification('reminder', 'email', 'sent')

        if channel in ('whatsapp', 'both'):
            wa_number = self._clean_wa_number(seafarer.whatsapp_number)
            if wa_number:
                self._send_whatsapp(wa_number, self._build_reminder_wa_message(ctx))
                self._log_notification('reminder', 'whatsapp', 'sent')

        self.write({'reminder_sent': True})
        self.message_post(body=_("Reminder H-3 sign on telah dikirim ke ABK."))

    def _send_sign_on_notification(self):
        """Notify operations team that crew has signed on."""
        self.ensure_one()
        self._log_notification('sign_on', 'email', 'sent')
        self.message_post(
            body=_("Sign on terkonfirmasi — %s naik ke %s.")
                 % (self.seafarer_id.display_name, self.vehicle_id.name),
            subtype_xmlid='mail.mt_note',
        )

    def _send_sign_off_notification(self):
        """Notify operations team that crew has signed off."""
        self.ensure_one()
        self._log_notification('sign_off', 'email', 'sent')
        self.message_post(
            body=_("Sign off terkonfirmasi — %s turun dari %s setelah %d hari.")
                 % (self.seafarer_id.display_name, self.vehicle_id.name,
                    self.sea_service_days),
            subtype_xmlid='mail.mt_note',
        )

    # ── Email helpers ──────────────────────────────────────────────────────

    def _send_schedule_email_fallback(self, email, ctx):
        """Send schedule notification via mail.mail (fallback jika template tidak ada)."""
        subject = (
            f"[{ctx['company_name']}] Jadwal Penugasan Kapal — "
            f"{ctx['vessel_name']} · Sign On {ctx['sign_on_date']}"
        )
        body = self._build_schedule_email_body(ctx)
        self.env['mail.mail'].create({
            'subject': subject,
            'body_html': body,
            'email_to': email,
            'auto_delete': True,
        }).send()

    def _send_reminder_email_fallback(self, email, ctx):
        subject = (
            f"[REMINDER] Sign On H-3 — {ctx['vessel_name']} · {ctx['sign_on_date']}"
        )
        body = self._build_reminder_email_body(ctx)
        self.env['mail.mail'].create({
            'subject': subject,
            'body_html': body,
            'email_to': email,
            'auto_delete': True,
        }).send()

    def _build_schedule_email_body(self, ctx):
        warnings_html = ''
        if ctx['cert_warnings']:
            warnings_html = f"""
            <div style="background:#FEF3C7;border-left:4px solid #F59E0B;padding:12px;margin:16px 0;border-radius:4px;">
              <b>⚠ Peringatan Sertifikat:</b><br/>
              <pre style="margin:8px 0 0;font-size:13px;">{ctx['cert_warnings']}</pre>
            </div>"""

        return f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:24px;">
          <div style="background:#0F6E56;color:#fff;padding:20px 24px;border-radius:8px 8px 0 0;">
            <h2 style="margin:0;font-size:20px;">Jadwal Penugasan Kapal</h2>
            <p style="margin:4px 0 0;opacity:.8;font-size:14px;">{ctx['company_name']}</p>
          </div>
          <div style="background:#fff;border:1px solid #e5e7eb;border-top:none;
                      padding:24px;border-radius:0 0 8px 8px;">
            <p>Yth. <b>{ctx['seafarer_name']}</b>,</p>
            <p>Anda telah dijadwalkan untuk bertugas dengan detail sebagai berikut:</p>
            <table style="width:100%;border-collapse:collapse;margin:16px 0;">
              <tr style="background:#F9FAFB;">
                <td style="padding:10px 12px;border:1px solid #e5e7eb;font-weight:bold;width:40%;">Kapal</td>
                <td style="padding:10px 12px;border:1px solid #e5e7eb;">{ctx['vessel_name']}</td>
              </tr>
              <tr>
                <td style="padding:10px 12px;border:1px solid #e5e7eb;font-weight:bold;">Jabatan</td>
                <td style="padding:10px 12px;border:1px solid #e5e7eb;">{ctx['rank_name']}</td>
              </tr>
              <tr style="background:#F9FAFB;">
                <td style="padding:10px 12px;border:1px solid #e5e7eb;font-weight:bold;">Tanggal Sign On</td>
                <td style="padding:10px 12px;border:1px solid #e5e7eb;color:#0F6E56;font-weight:bold;">{ctx['sign_on_date']}</td>
              </tr>
              <tr>
                <td style="padding:10px 12px;border:1px solid #e5e7eb;font-weight:bold;">Pelabuhan Sign On</td>
                <td style="padding:10px 12px;border:1px solid #e5e7eb;">{ctx['sign_on_port']}</td>
              </tr>
              <tr style="background:#F9FAFB;">
                <td style="padding:10px 12px;border:1px solid #e5e7eb;font-weight:bold;">Estimasi Sign Off</td>
                <td style="padding:10px 12px;border:1px solid #e5e7eb;">{ctx['sign_off_date']}</td>
              </tr>
            </table>
            {warnings_html}
            <p style="color:#6B7280;font-size:13px;">
              Mohon konfirmasikan kehadiran Anda dengan membalas email ini atau
              menghubungi bagian operasional. Pastikan seluruh dokumen dan sertifikat
              Anda valid sebelum tanggal sign on.
            </p>
            <p style="color:#6B7280;font-size:12px;border-top:1px solid #e5e7eb;
                      padding-top:16px;margin-top:24px;">
              Email ini dikirim otomatis oleh sistem. Hubungi HRD/Operasional
              jika ada pertanyaan.<br/>{ctx['company_name']}
            </p>
          </div>
        </div>"""

    def _build_reminder_email_body(self, ctx):
        return f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:24px;">
          <div style="background:#854F0B;color:#fff;padding:20px 24px;border-radius:8px 8px 0 0;">
            <h2 style="margin:0;font-size:20px;">Pengingat — Sign On 3 Hari Lagi</h2>
            <p style="margin:4px 0 0;opacity:.8;font-size:14px;">{ctx['company_name']}</p>
          </div>
          <div style="background:#fff;border:1px solid #e5e7eb;border-top:none;
                      padding:24px;border-radius:0 0 8px 8px;">
            <p>Yth. <b>{ctx['seafarer_name']}</b>,</p>
            <p>Ini adalah pengingat bahwa Anda dijadwalkan <b>sign on 3 hari lagi</b>:</p>
            <ul style="line-height:2;">
              <li><b>Kapal:</b> {ctx['vessel_name']}</li>
              <li><b>Jabatan:</b> {ctx['rank_name']}</li>
              <li><b>Tanggal Sign On:</b> <span style="color:#854F0B;font-weight:bold;">{ctx['sign_on_date']}</span></li>
              <li><b>Pelabuhan:</b> {ctx['sign_on_port']}</li>
            </ul>
            <p>Pastikan dokumen dan sertifikat Anda sudah siap. Segera hubungi
               operasional jika ada kendala kehadiran.</p>
          </div>
        </div>"""

    # ── WhatsApp helpers ───────────────────────────────────────────────────

    def _clean_wa_number(self, number):
        """Normalize WA number to international format 628xxxxxxxxx."""
        if not number:
            return None
        n = re.sub(r'\D', '', number)
        if n.startswith('08'):
            n = '62' + n[1:]
        elif n.startswith('8') and len(n) == 10:
            n = '62' + n
        if not n.startswith('62') or len(n) < 10:
            return None
        return n

    def _send_whatsapp(self, wa_number, message):
        """
        Send WhatsApp message via configured gateway.
        Mendukung:
          1. Odoo 17+ native WhatsApp (module whatsapp)
          2. Fallback: WA Business API gateway via ir.config_parameter
        """
        self.ensure_one()
        sent = False

        # Coba Odoo native WhatsApp module jika tersedia
        if 'whatsapp.message' in self.env:
            try:
                self.env['whatsapp.message'].create({
                    'mobile_number': wa_number,
                    'body': message,
                    'res_model': self._name,
                    'res_id': self.id,
                }).button_send_message()
                sent = True
                _logger.info("WA sent via Odoo native to %s", wa_number)
            except Exception as e:
                _logger.warning("Odoo WA module failed: %s", str(e))

        # Fallback: HTTP gateway (fonnte, wablas, dll)
        if not sent:
            self._send_wa_via_gateway(wa_number, message)

    def _send_wa_via_gateway(self, wa_number, message):
        """Send via external WA HTTP gateway (configurable)."""
        import requests
        ICP = self.env['ir.config_parameter'].sudo()
        gateway_url = ICP.get_param('vessel_crew.wa_gateway_url', '')
        gateway_token = ICP.get_param('vessel_crew.wa_gateway_token', '')

        if not gateway_url or not gateway_token:
            _logger.warning(
                "WA gateway tidak dikonfigurasi. "
                "Set vessel_crew.wa_gateway_url dan vessel_crew.wa_gateway_token "
                "di System Parameters."
            )
            return

        try:
            payload = {
                'target': wa_number,
                'message': message,
            }
            headers = {
                'Authorization': gateway_token,
                'Content-Type': 'application/json',
            }
            resp = requests.post(
                gateway_url, json=payload, headers=headers, timeout=10,
            )
            if resp.status_code == 200:
                _logger.info("WA gateway sent to %s", wa_number)
            else:
                _logger.warning(
                    "WA gateway error %s: %s", resp.status_code, resp.text[:200]
                )
        except Exception as e:
            _logger.error("WA gateway exception: %s", str(e))

    def _build_schedule_wa_message(self, ctx):
        msg = (
            f"*📋 Jadwal Penugasan Kapal*\n"
            f"Dari: {ctx['company_name']}\n\n"
            f"Yth. Sdr/i *{ctx['seafarer_name']}*,\n\n"
            f"Anda dijadwalkan bertugas:\n"
            f"• 🚢 Kapal: *{ctx['vessel_name']}*\n"
            f"• ⚓ Jabatan: *{ctx['rank_name']}*\n"
            f"• 📅 Sign On: *{ctx['sign_on_date']}*\n"
            f"• 🏁 Pelabuhan: *{ctx['sign_on_port']}*\n"
            f"• 📅 Est. Sign Off: *{ctx['sign_off_date']}*\n"
        )
        if ctx['cert_warnings']:
            msg += f"\n⚠️ *Peringatan Sertifikat:*\n{ctx['cert_warnings']}\n"
        msg += (
            "\nMohon konfirmasi kehadiran Anda. "
            "Hubungi operasional jika ada kendala."
        )
        return msg

    def _build_reminder_wa_message(self, ctx):
        return (
            f"⏰ *REMINDER — Sign On 3 Hari Lagi*\n\n"
            f"Yth. Sdr/i *{ctx['seafarer_name']}*,\n\n"
            f"Pengingat jadwal penugasan Anda:\n"
            f"• 🚢 Kapal: *{ctx['vessel_name']}*\n"
            f"• ⚓ Jabatan: *{ctx['rank_name']}*\n"
            f"• 📅 Sign On: *{ctx['sign_on_date']}*\n"
            f"• 🏁 Pelabuhan: *{ctx['sign_on_port']}*\n\n"
            f"Pastikan dokumen & sertifikat Anda sudah siap.\n"
            f"Segera hubungi operasional jika ada kendala. ✅"
        )

    # ─────────────────────────────────────────────────────────────────────
    # Notification log helper
    # ─────────────────────────────────────────────────────────────────────

    def _log_notification(self, notif_type, channel, status, notes=''):
        self.ensure_one()
        self.env['vessel.notification.log'].create({
            'assignment_id': self.id,
            'notification_type': notif_type,
            'channel': channel,
            'status': status,
            'notes': notes,
            'sent_at': fields.Datetime.now(),
        })

    # ─────────────────────────────────────────────────────────────────────
    # Cron jobs
    # ─────────────────────────────────────────────────────────────────────

    def cron_send_reminder_h3(self):
        """Cron harian: kirim reminder H-3 sebelum sign on."""
        target_date = date.today() + timedelta(days=3)
        assignments = self.search([
            ('state', '=', 'confirmed'),
            ('sign_on_date', '=', target_date),
            ('reminder_sent', '=', False),
        ])
        _logger.info(
            "Cron H-3 reminder: ditemukan %d assignment untuk tanggal %s",
            len(assignments), target_date,
        )
        for assignment in assignments:
            try:
                assignment._send_reminder_notification()
            except Exception as e:
                _logger.error(
                    "Gagal kirim reminder untuk assignment %s: %s",
                    assignment.id, str(e),
                )

    def cron_check_overdue_sign_on(self):
        """Cron harian: flag assignment yang melewati tanggal sign on tanpa konfirmasi."""
        today = date.today()
        overdue = self.search([
            ('state', '=', 'confirmed'),
            ('sign_on_date', '<', today),
        ])
        for rec in overdue:
            rec.message_post(
                body=_(
                    "⚠ Peringatan: Tanggal sign on rencana (%s) sudah terlewat "
                    "namun ABK belum konfirmasi naik kapal. Silakan update status "
                    "atau hubungi ABK segera."
                ) % rec.sign_on_date,
            )


class VesselNotificationLog(models.Model):
    _name = 'vessel.notification.log'
    _description = 'Log Notifikasi ABK'
    _order = 'sent_at desc'

    assignment_id = fields.Many2one(
        'vessel.crew.assignment', string='Penugasan',
        ondelete='cascade', index=True,
    )
    notification_type = fields.Selection([
        ('schedule', 'Jadwal Sign On'),
        ('reminder', 'Reminder H-3'),
        ('sign_on', 'Konfirmasi Sign On'),
        ('sign_off', 'Konfirmasi Sign Off'),
        ('cert_warning', 'Peringatan Sertifikat'),
    ], string='Tipe Notifikasi', required=True)
    channel = fields.Selection([
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
    ], string='Kanal', required=True)
    status = fields.Selection([
        ('sent', 'Terkirim'),
        ('failed', 'Gagal'),
        ('pending', 'Pending'),
    ], string='Status', default='pending')
    sent_at = fields.Datetime(string='Waktu Kirim')
    notes = fields.Text(string='Catatan / Error')
