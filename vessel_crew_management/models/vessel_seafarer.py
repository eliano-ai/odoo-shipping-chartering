from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


MANNING_POOL_STATUS = [
    ('available', 'Tersedia'),
    ('on_board', 'Di Kapal'),
    ('on_leave', 'Cuti'),
    ('training', 'Pelatihan'),
    ('medical', 'Cuti Medis'),
    ('standby', 'Standby'),
    ('terminated', 'Tidak Aktif'),
]

COC_GRADE = [
    ('ANT_I', 'ANT-I (Ahli Nautika Tingkat I / Nahkoda)'),
    ('ANT_II', 'ANT-II (Ahli Nautika Tingkat II)'),
    ('ANT_III', 'ANT-III (Ahli Nautika Tingkat III)'),
    ('ANT_IV', 'ANT-IV'),
    ('ANT_V', 'ANT-V'),
    ('ATT_I', 'ATT-I (Ahli Teknika Tingkat I / KKM)'),
    ('ATT_II', 'ATT-II'),
    ('ATT_III', 'ATT-III'),
    ('ATT_IV', 'ATT-IV'),
    ('ATT_V', 'ATT-V'),
    ('BST', 'BST only (Rating)'),
    ('other', 'Lainnya'),
]


class VesselSeafarer(models.Model):
    _name = 'vessel.seafarer'
    _description = 'Data ABK Kapal (Seafarer)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'
    _order = 'vessel_rank_id, employee_id'

    # ── Link ke hr.employee ────────────────────────────────────────────────
    employee_id = fields.Many2one(
        'hr.employee', string='Karyawan',
        required=True, ondelete='cascade',
        index=True,
        help='Pilih karyawan yang akan dijadikan ABK. '
             'Satu karyawan hanya boleh punya satu record seafarer.',
    )
    display_name = fields.Char(
        compute='_compute_display_name', store=True,
    )
    name = fields.Char(related='employee_id.name', store=True, string='Nama')
    work_email = fields.Char(
        related='employee_id.work_email', store=True, string='Email Kerja',
    )
    mobile_phone = fields.Char(
        related='employee_id.mobile_phone', store=True, string='No. HP',
    )
    company_id = fields.Many2one(
        related='employee_id.company_id', store=True,
    )
    image_128 = fields.Image(related='employee_id.image_128')

    # ── Identitas Pelaut ───────────────────────────────────────────────────
    vessel_rank_id = fields.Many2one(
        'vessel.crew.rank', string='Jabatan / Rank',
        tracking=True,
        help='Jabatan ABK saat ini (bisa berbeda dengan jabatan di assignment tertentu).',
    )
    buku_pelaut_no = fields.Char(
        string='No. Buku Pelaut',
        tracking=True,
        help='Nomor Buku Pelaut — diterbitkan Ditjen Hubla. Format: BP-XXXXXX',
    )
    buku_pelaut_expiry = fields.Date(
        string='Berlaku Hingga (Buku Pelaut)',
        tracking=True,
    )
    coc_number = fields.Char(
        string='No. CoC / ATKAPAL',
        tracking=True,
        help='Nomor Certificate of Competency — Sertifikat Keahlian Pelaut',
    )
    coc_grade = fields.Selection(
        COC_GRADE, string='Kelas CoC',
        tracking=True,
    )
    coc_expiry = fields.Date(
        string='Berlaku Hingga (CoC)',
        tracking=True,
    )
    seaman_book_no = fields.Char(
        string='No. Seaman Book (Internasional)',
        help='Untuk ABK yang memiliki buku pelaut internasional selain Buku Pelaut Indonesia.',
    )

    # ── Data Pribadi Pelaut ────────────────────────────────────────────────
    nationality = fields.Char(
        string='Kewarganegaraan', default='Indonesia',
    )
    place_of_birth = fields.Char(string='Tempat Lahir')
    home_port = fields.Char(
        string='Kota Asal / Pelabuhan Asal',
        help='Kota asal ABK — digunakan untuk kalkulasi biaya repatriasi (MLC 2006)',
    )
    emergency_contact_name = fields.Char(string='Nama Kontak Darurat')
    emergency_contact_phone = fields.Char(string='No. HP Kontak Darurat')
    emergency_contact_relation = fields.Char(
        string='Hubungan',
        help='Misal: Istri, Suami, Orang Tua, dll',
    )
    whatsapp_number = fields.Char(
        string='No. WhatsApp',
        help='Nomor WhatsApp untuk notifikasi jadwal. Format internasional: 628xxxxxxxxxx',
        tracking=True,
    )

    # ── Status di Manning Pool ─────────────────────────────────────────────
    manning_pool_status = fields.Selection(
        MANNING_POOL_STATUS, string='Status',
        default='available', tracking=True,
        index=True,
    )
    current_assignment_id = fields.Many2one(
        'vessel.crew.assignment', string='Penugasan Aktif',
        compute='_compute_current_assignment', store=False,
    )
    current_vessel_id = fields.Many2one(
        'fleet.vehicle', string='Kapal Saat Ini',
        compute='_compute_current_assignment', store=False,
    )

    # ── Sea Service Summary ────────────────────────────────────────────────
    total_sea_service_days = fields.Integer(
        compute='_compute_sea_service_summary',
        string='Total Hari di Laut',
        help='Akumulasi hari di kapal dari semua assignment yang completed.',
    )
    assignment_count = fields.Integer(
        compute='_compute_sea_service_summary',
        string='Total Penugasan',
    )
    assignment_ids = fields.One2many(
        'vessel.crew.assignment', 'seafarer_id',
        string='Riwayat Penugasan',
    )
    sea_service_log_ids = fields.One2many(
        'vessel.sea.service.log', 'seafarer_id',
        string='Sea Service Log',
    )

    # ── Cert / Dokumen ─────────────────────────────────────────────────────
    cert_document_ids = fields.One2many(
        'fleet.vehicle.document', 'crew_id',
        string='Sertifikat & Dokumen',
        domain=[('is_vessel_doc', '=', True)],
    )
    cert_expiring_count = fields.Integer(
        compute='_compute_cert_status',
        string='Cert Akan Expired',
    )
    cert_expired_count = fields.Integer(
        compute='_compute_cert_status',
        string='Cert Sudah Expired',
    )
    has_critical_cert_issue = fields.Boolean(
        compute='_compute_cert_status', store=True,
        string='Ada Masalah Cert Kritis',
    )

    # ── Constraint ────────────────────────────────────────────────────────
    _sql_constraints = [
        ('employee_uniq', 'unique(employee_id)',
         'Satu karyawan hanya boleh memiliki satu record ABK.'),
    ]

    # ─────────────────────────────────────────────────────────────────────
    # Compute
    # ─────────────────────────────────────────────────────────────────────

    @api.depends('employee_id', 'vessel_rank_id')
    def _compute_display_name(self):
        for rec in self:
            name = rec.employee_id.name or ''
            rank = rec.vessel_rank_id.name or ''
            rec.display_name = f"{name} — {rank}" if rank else name

    def _compute_current_assignment(self):
        Assignment = self.env['vessel.crew.assignment']
        for rec in self:
            active = Assignment.search([
                ('seafarer_id', '=', rec.id),
                ('state', '=', 'on_board'),
            ], limit=1)
            rec.current_assignment_id = active
            rec.current_vessel_id = active.vehicle_id if active else False

    @api.depends('assignment_ids', 'assignment_ids.state',
                 'assignment_ids.sea_service_days')
    def _compute_sea_service_summary(self):
        for rec in self:
            completed = rec.assignment_ids.filtered(
                lambda a: a.state == 'completed'
            )
            rec.total_sea_service_days = sum(completed.mapped('sea_service_days'))
            rec.assignment_count = len(rec.assignment_ids)

    @api.depends('cert_document_ids', 'cert_document_ids.state')
    def _compute_cert_status(self):
        for rec in self:
            certs = rec.cert_document_ids
            rec.cert_expiring_count = len(
                certs.filtered(lambda c: c.state == 'expiring_soon')
            )
            rec.cert_expired_count = len(
                certs.filtered(lambda c: c.state == 'expired')
            )
            rec.has_critical_cert_issue = rec.cert_expired_count > 0

    # ─────────────────────────────────────────────────────────────────────
    # Business methods
    # ─────────────────────────────────────────────────────────────────────

    def get_expired_certs(self):
        """Return list of expired/expiring cert names for notification."""
        self.ensure_one()
        issues = []
        for cert in self.cert_document_ids:
            if cert.state == 'expired':
                issues.append(f"[EXPIRED] {cert.doc_type_id.name or cert.doc_type} — {cert.expiry_date}")
            elif cert.state == 'expiring_soon':
                issues.append(f"[Segera Expired] {cert.doc_type_id.name or cert.doc_type} — {cert.expiry_date} ({cert.days_remaining} hari lagi)")
        return issues

    def action_view_assignments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Penugasan — %s') % self.display_name,
            'res_model': 'vessel.crew.assignment',
            'view_mode': 'list,form',
            'domain': [('seafarer_id', '=', self.id)],
        }

    def action_view_sea_service(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sea Service Log — %s') % self.display_name,
            'res_model': 'vessel.sea.service.log',
            'view_mode': 'list',
            'domain': [('seafarer_id', '=', self.id)],
        }


class VesselSeaServiceLog(models.Model):
    _name = 'vessel.sea.service.log'
    _description = 'Sea Service Log ABK'
    _order = 'from_date desc'
    _rec_name = 'display_name'

    assignment_id = fields.Many2one(
        'vessel.crew.assignment', string='Referensi Penugasan',
        ondelete='cascade', index=True,
    )
    seafarer_id = fields.Many2one(
        'vessel.seafarer', string='ABK',
        required=True, ondelete='cascade', index=True,
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Kapal',
        required=True,
    )
    rank_id = fields.Many2one(
        'vessel.crew.rank', string='Jabatan saat itu',
    )
    from_date = fields.Date(string='Tanggal Sign On', required=True)
    to_date = fields.Date(string='Tanggal Sign Off', required=True)
    days = fields.Integer(
        string='Jumlah Hari',
        compute='_compute_days', store=True,
    )
    sign_on_port = fields.Char(string='Pelabuhan Sign On')
    sign_off_port = fields.Char(string='Pelabuhan Sign Off')
    vessel_name = fields.Char(string='Nama Kapal (saat itu)')
    vessel_gt = fields.Char(string='GT Kapal')
    vessel_flag = fields.Char(string='Bendera Kapal')
    notes = fields.Text(string='Catatan')
    display_name = fields.Char(compute='_compute_display_name')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company,
    )

    @api.depends('from_date', 'to_date')
    def _compute_days(self):
        for rec in self:
            if rec.from_date and rec.to_date:
                rec.days = (rec.to_date - rec.from_date).days
            else:
                rec.days = 0

    @api.depends('seafarer_id', 'vehicle_id', 'from_date')
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.seafarer_id:
                parts.append(rec.seafarer_id.name or '')
            if rec.vehicle_id:
                parts.append(rec.vehicle_id.name or '')
            if rec.from_date:
                parts.append(str(rec.from_date))
            rec.display_name = ' · '.join(filter(None, parts))
