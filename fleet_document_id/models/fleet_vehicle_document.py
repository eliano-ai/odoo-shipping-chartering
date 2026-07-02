from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, timedelta


DOC_TYPE_SELECTION = [
    ('stnk', 'STNK (Surat Tanda Nomor Kendaraan)'),
    ('bpkb', 'BPKB (Buku Pemilik Kendaraan Bermotor)'),
    ('kir', 'KIR / Uji Berkala'),
    ('sim', 'SIM (Surat Izin Mengemudi)'),
    ('asuransi', 'Asuransi Kendaraan'),
    ('emisi', 'Uji Emisi'),
    ('dispensasi', 'Dispensasi Tonase / Rute'),
    ('lainnya', 'Lainnya'),
]

SIM_TYPE_SELECTION = [
    ('A', 'SIM A — Kendaraan roda 4 < 3.5 ton'),
    ('A_umum', 'SIM A Umum — Angkutan penumpang'),
    ('B1', 'SIM B1 — Kendaraan > 3.5 ton'),
    ('B1_umum', 'SIM B1 Umum — Angkutan penumpang besar'),
    ('B2', 'SIM B2 — Kendaraan gandeng / tempelan'),
    ('B2_umum', 'SIM B2 Umum — Angkutan barang gandeng'),
    ('C', 'SIM C — Kendaraan roda 2'),
    ('D', 'SIM D — Kendaraan khusus disabilitas'),
]

STATE_SELECTION = [
    ('valid', 'Valid'),
    ('expiring_soon', 'Segera Expired'),
    ('expired', 'Expired'),
    ('missing', 'Tidak Ada'),
]


class FleetVehicleDocument(models.Model):
    _name = 'fleet.vehicle.document'
    _description = 'Fleet Vehicle Document Indonesia'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'expiry_date asc, vehicle_id'
    _rec_name = 'display_name'

    # ── Core fields ─────────────────────────────────────────────────────────
    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Kendaraan',
        ondelete='cascade', index=True,
        domain=[('active', '=', True)],
    )

    # ── doc_type lama — DEPRECATED, dipertahankan untuk data existing ───────
    # Jangan hapus field ini sampai semua record sudah dimigrasi ke doc_type_id
    doc_type = fields.Selection(
        DOC_TYPE_SELECTION, string='Jenis Dokumen (Lama)',
        tracking=True,
        help='[DEPRECATED] Field lama untuk kendaraan darat. '
             'Gunakan "Tipe Dokumen" (doc_type_id) untuk record baru.',
    )

    # ── doc_type_id baru — Many2one ke master fleet.document.type ────────────
    doc_type_id = fields.Many2one(
        'fleet.document.type', string='Tipe Dokumen',
        tracking=True, index=True,
        help='Pilih tipe dokumen dari master. Untuk kapal, hanya tampil '
             'dokumen yang sesuai tipe kapal.',
    )
    doc_category = fields.Selection(
        related='doc_type_id.category', string='Kategori Dokumen',
        store=True, readonly=True,
    )
    is_vessel_doc = fields.Boolean(
        compute='_compute_is_vessel_doc', store=True,
        string='Dokumen Kapal',
    )

    # ── Computed domain untuk filter doc_type_id berdasarkan kapal ───────────
    vessel_type_id = fields.Many2one(
        related='vehicle_id.vessel_type_id',
        string='Tipe Kapal', readonly=True, store=False,
    )

    # ── Field SIM dan pengemudi — hanya untuk kendaraan DARAT ────────────────
    sim_type = fields.Selection(
        SIM_TYPE_SELECTION, string='Kategori SIM',
        help='Wajib diisi jika jenis dokumen adalah SIM (kendaraan darat)',
    )
    driver_id = fields.Many2one(
        'hr.employee', string='Pengemudi',
        help='Wajib diisi jika jenis dokumen adalah SIM (kendaraan darat)',
        tracking=True,
    )

    # ── Field ABK / Crew — hanya untuk KAPAL LAUT ────────────────────────────
    crew_id = fields.Many2one(
        'hr.employee', string='ABK / Crew',
        tracking=True,
        help='Diisi jika dokumen ini melekat pada individu ABK '
             '(Sijil Nahkoda, Sertifikat STCW, Buku Pelaut, dll).',
    )
    crew_rank = fields.Char(
        string='Jabatan / Rank ABK',
        help='Jabatan ABK saat dokumen diterbitkan, misal: Nahkoda, KKM, Mualim I, dll.',
    )
    doc_number = fields.Char(
        string='Nomor Dokumen',
        help='Nomor STNK, nomor polis asuransi, nomor SIM, dll',
        tracking=True,
    )
    issuing_authority = fields.Char(
        string='Instansi Penerbit',
        help='Samsat, Dishub, Polri, nama perusahaan asuransi, dll',
    )
    issue_date = fields.Date(string='Tanggal Terbit', tracking=True)
    expiry_date = fields.Date(
        string='Berlaku Hingga',
        required=True, tracking=True,
        index=True,
    )
    # ── Alert config ─────────────────────────────────────────────────────────
    alert_threshold_days = fields.Integer(
        string='Alert Sebelum Expired (hari)',
        default=30,
        help='Mulai kirim notifikasi berapa hari sebelum expired. Default: 30 hari.',
    )
    renewal_pic_id = fields.Many2one(
        'res.users', string='PIC Perpanjangan',
        help='User yang bertanggung jawab mengurus perpanjangan dokumen ini',
    )
    # ── Financial ────────────────────────────────────────────────────────────
    renewal_cost = fields.Monetary(
        string='Biaya Perpanjangan Terakhir',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency', string='Mata Uang',
        default=lambda self: self.env.ref('base.IDR', raise_if_not_found=False),
    )
    # ── Intermediate survey (kapal) ───────────────────────────────────────────
    next_survey_date = fields.Date(
        string="Tanggal Survey Berikutnya",
        help="Untuk sertifikat BKI / class yang ada intermediate survey-nya. "
             "Bisa diisi manual atau otomatis dari master tipe dokumen.",
    )
    survey_alert_sent = fields.Boolean(
        string="Alert Survey Terkirim", default=False,
    )

    # ── Attachments ──────────────────────────────────────────────────────────
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Dokumen Terlampir',
        help='Upload scan / foto dokumen (PDF, JPG, PNG)',
    )
    attachment_count = fields.Integer(
        compute='_compute_attachment_count', string='Jumlah Lampiran',
    )
    # ── Renewal history ──────────────────────────────────────────────────────
    renewal_log_ids = fields.One2many(
        'fleet.document.renewal.log', 'document_id',
        string='Riwayat Perpanjangan',
    )
    renewal_count = fields.Integer(
        compute='_compute_renewal_count', string='Total Perpanjangan',
    )
    # ── Computed: state & days ────────────────────────────────────────────────
    state = fields.Selection(
        STATE_SELECTION, string='Status',
        compute='_compute_state', store=True,
        tracking=True,
    )
    days_remaining = fields.Integer(
        string='Sisa Hari',
        compute='_compute_state', store=True,
    )
    note = fields.Text(string='Catatan')
    company_id = fields.Many2one(
        'res.company', string='Perusahaan',
        default=lambda self: self.env.company, required=True,
    )
    active = fields.Boolean(default=True)

    # ── Display name ─────────────────────────────────────────────────────────
    display_name = fields.Char(compute='_compute_display_name', store=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Compute methods
    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('doc_type', 'doc_type_id', 'vehicle_id', 'driver_id', 'crew_id', 'sim_type')
    def _compute_display_name(self):
        for rec in self:
            # Prioritaskan doc_type_id (baru); fallback ke doc_type (lama)
            if rec.doc_type_id:
                doc_label = rec.doc_type_id.name
            else:
                doc_label = dict(DOC_TYPE_SELECTION).get(rec.doc_type, rec.doc_type or '')

            # Dokumen SIM darat (logika lama)
            if rec.doc_type == 'sim' and rec.driver_id:
                sim_label = dict(SIM_TYPE_SELECTION).get(rec.sim_type, '') if rec.sim_type else ''
                rec.display_name = f"{doc_label} {sim_label} — {rec.driver_id.name}"
            # Dokumen kapal yang melekat pada crew
            elif rec.doc_type_id and rec.doc_type_id.requires_crew and rec.crew_id:
                rec.display_name = f"{doc_label} — {rec.crew_id.name}"
            elif rec.vehicle_id:
                rec.display_name = f"{doc_label} — {rec.vehicle_id.license_plate or rec.vehicle_id.name}"
            else:
                rec.display_name = doc_label

    @api.depends('doc_type_id', 'vehicle_id')
    def _compute_is_vessel_doc(self):
        for rec in self:
            if rec.doc_type_id:
                rec.is_vessel_doc = rec.doc_type_id.category in ('vessel', 'both')
            elif rec.vehicle_id and rec.vehicle_id.is_vessel:
                rec.is_vessel_doc = True
            else:
                rec.is_vessel_doc = False

    @api.onchange('doc_type_id')
    def _onchange_doc_type_id(self):
        # Auto-fill alert_threshold_days dari master jika ada
        if self.doc_type_id and self.doc_type_id.default_alert_days:
            self.alert_threshold_days = self.doc_type_id.default_alert_days
        # Auto-hitung next_survey_date jika ada interval survey
        if self.doc_type_id and self.doc_type_id.has_survey_interval and self.issue_date:
            from dateutil.relativedelta import relativedelta
            self.next_survey_date = self.issue_date + relativedelta(
                months=self.doc_type_id.survey_interval_months
            )

    def _get_doc_type_domain(self):
        """Helper untuk domain doc_type_id berdasarkan tipe kapal kendaraan."""
        if self.vehicle_id and self.vehicle_id.is_vessel:
            vessel_type = self.vehicle_id.vessel_type_id
            if vessel_type:
                return [
                    ('category', 'in', ['vessel', 'both']),
                    '|',
                    ('applicable_vessel_types', '=', False),
                    ('applicable_vessel_types', 'in', [vessel_type.id]),
                ]
            return [('category', 'in', ['vessel', 'both'])]
        return [('category', 'in', ['land', 'both'])]

    @api.depends('expiry_date', 'alert_threshold_days')
    def _compute_state(self):
        today = date.today()
        for rec in self:
            if not rec.expiry_date:
                rec.days_remaining = 0
                rec.state = 'missing'
                continue
            delta = (rec.expiry_date - today).days
            rec.days_remaining = delta
            if delta < 0:
                rec.state = 'expired'
            elif delta <= rec.alert_threshold_days:
                rec.state = 'expiring_soon'
            else:
                rec.state = 'valid'

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = len(rec.attachment_ids)

    # ✅ FIX: Tambahkan @api.depends
    @api.depends('renewal_log_ids')
    def _compute_renewal_count(self):
        for rec in self:
            rec.renewal_count = len(rec.renewal_log_ids)

    # ─────────────────────────────────────────────────────────────────────────
    # Constraints
    # ─────────────────────────────────────────────────────────────────────────

    @api.constrains('issue_date', 'expiry_date')
    def _check_dates(self):
        for rec in self:
            if rec.issue_date and rec.expiry_date and rec.issue_date > rec.expiry_date:
                raise ValidationError(_(
                    "Tanggal terbit tidak boleh lebih besar dari tanggal berlaku hingga.\n"
                    "Dokumen: %s"
                ) % rec.display_name)

    @api.constrains('doc_type', 'driver_id', 'sim_type')
    def _check_sim_fields(self):
        for rec in self:
            if rec.doc_type == 'sim':
                if not rec.driver_id:
                    raise ValidationError(_(
                        "Pengemudi wajib diisi untuk dokumen SIM.\n"
                        "Silakan pilih pengemudi terlebih dahulu."
                    ))
                if not rec.sim_type:
                    raise ValidationError(_(
                        "Kategori SIM wajib diisi (SIM A, B1, B2, dll)."
                    ))

    @api.constrains('doc_type', 'vehicle_id', 'driver_id')
    def _check_vehicle_or_driver(self):
        for rec in self:
            if rec.doc_type != 'sim' and not rec.vehicle_id:
                raise ValidationError(_(
                    "Kendaraan wajib diisi untuk dokumen tipe '%s'."
                ) % dict(DOC_TYPE_SELECTION).get(rec.doc_type, rec.doc_type))

    # ─────────────────────────────────────────────────────────────────────────
    # Scheduled action — dipanggil dari cron harian
    # ─────────────────────────────────────────────────────────────────────────

    @api.model
    def _cron_check_expiry_and_notify(self):
        today = date.today()
        alert_levels = [
            (30, 'fleet_document_id.email_template_doc_alert_30', False),
            (7,  'fleet_document_id.email_template_doc_alert_7', False),
            (0,  'fleet_document_id.email_template_doc_expired', False),
            (-7, 'fleet_document_id.email_template_doc_overdue', True),
        ]
        for days_trigger, template_xmlid, is_overdue in alert_levels:
            target_date = today + timedelta(days=days_trigger) if days_trigger >= 0 \
                else today - timedelta(days=abs(days_trigger))

            documents = self.search([
                ('expiry_date', '=', target_date),
                ('active', '=', True),
            ])
            if not documents:
                continue
            template = self.env.ref(template_xmlid, raise_if_not_found=False)
            if not template:
                continue
            for doc in documents:
                try:
                    template.send_mail(doc.id, force_send=True, raise_exception=False)
                except Exception:
                    pass

        all_docs = self.search([('active', '=', True)])
        all_docs._compute_state()

    # ─────────────────────────────────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────────────────────────────────

    def action_open_renewal_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Perpanjang Dokumen'),
            'res_model': 'fleet.document.renewal.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_document_id': self.id,
                'default_vehicle_id': self.vehicle_id.id,
                'default_doc_type': self.doc_type,
                'default_current_expiry': self.expiry_date,
            },
        }

    def action_view_attachments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lampiran Dokumen'),
            'res_model': 'ir.attachment',
            'view_mode': 'kanban,list,form',
            'domain': [('id', 'in', self.attachment_ids.ids)],
            'target': 'current',
        }

    # ✅ FIX: Tambahkan method baru ini
    def action_view_renewal_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Riwayat Perpanjangan'),
            'res_model': 'fleet.document.renewal.log',
            'view_mode': 'list,form',
            'domain': [('document_id', '=', self.id)],
            'context': {
                'default_document_id': self.id,
            },
        }