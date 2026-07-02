from odoo import api, fields, models, _
from odoo.exceptions import UserError


VESSEL_OPERATION_AREA = [
    ('domestic', 'Pelayaran Dalam Negeri'),
    ('international', 'Pelayaran Internasional'),
    ('local', 'Pelayaran Lokal / Rakyat'),
]


REQUIRED_LICENSE_TYPES = [
    ('A', 'SIM A'),
    ('A_umum', 'SIM A Umum'),
    ('B1', 'SIM B1'),
    ('B1_umum', 'SIM B1 Umum'),
    ('B2', 'SIM B2'),
    ('B2_umum', 'SIM B2 Umum'),
    ('C', 'SIM C'),
    ('none', 'Tidak Diperlukan SIM Khusus'),
]

DOC_STATUS = [
    ('ok', 'Semua Dokumen Valid'),
    ('warning', 'Ada Dokumen Hampir Expired'),
    ('critical', 'Ada Dokumen Expired'),
    ('incomplete', 'Dokumen Tidak Lengkap'),
]


class FleetVehicleExtend(models.Model):
    _inherit = 'fleet.vehicle'

    # ── Document relation ────────────────────────────────────────────────────
    document_ids = fields.One2many(
        'fleet.vehicle.document', 'vehicle_id',
        string='Dokumen Legal',
    )
    document_count = fields.Integer(
        compute='_compute_document_summary', string='Jumlah Dokumen',
    )
    # ── Aggregated status ────────────────────────────────────────────────────
    doc_status = fields.Selection(
        DOC_STATUS, string='Status Dokumen',
        compute='_compute_document_summary', store=True,
    )
    expired_doc_count = fields.Integer(
        compute='_compute_document_summary', string='Dokumen Expired', store=True,
    )
    expiring_doc_count = fields.Integer(
        compute='_compute_document_summary', string='Dokumen Hampir Expired', store=True,
    )
    next_expiry_date = fields.Date(
        compute='_compute_document_summary', string='Expired Terdekat', store=True,
    )
    next_expiry_doc = fields.Char(
        compute='_compute_document_summary', string='Dokumen Hampir Expired', store=True,
    )
    # ── Vessel identification ─────────────────────────────────────────────────
    vessel_type_id = fields.Many2one(
        'fleet.document.vessel.type', string='Tipe Kapal',
        help='Tentukan tipe kapal. Jika diisi, kendaraan ini dianggap sebagai kapal laut '
             'dan form akan menampilkan dokumen-dokumen yang relevan untuk kapal.',
        tracking=True,
    )
    is_vessel = fields.Boolean(
        compute='_compute_is_vessel', store=True,
        string='Adalah Kapal Laut',
        help='True jika kendaraan ini adalah kapal laut (vessel_type_id terisi).',
    )
    call_sign = fields.Char(
        string='Call Sign',
        help='Tanda panggil radio kapal, misal: YBXXX',
    )
    imo_number = fields.Char(
        string='Nomor IMO',
        help='IMO number — 7 digit, unik untuk setiap kapal. Format: IMO 1234567',
    )
    gross_tonnage = fields.Float(
        string='Gross Tonnage (GT)',
        help='Gross Tonnage kapal sesuai Surat Ukur.',
    )
    net_tonnage = fields.Float(
        string='Net Tonnage (NT)',
    )
    deadweight_tonnage = fields.Float(
        string='DWT (ton)',
        help='Deadweight Tonnage — kapasitas muat kapal.',
    )
    flag_state = fields.Char(
        string='Negara Bendera',
        default='Indonesia',
        help='Negara tempat kapal didaftarkan.',
    )
    port_of_registry = fields.Char(
        string='Pelabuhan Pendaftaran',
        help='Pelabuhan asal kapal terdaftar, misal: Jakarta, Surabaya, Makassar.',
    )
    operation_area = fields.Selection(
        VESSEL_OPERATION_AREA, string='Daerah Pelayaran',
        help='Menentukan jenis sertifikasi yang diperlukan.',
    )
    classification_society = fields.Char(
        string='Biro Klasifikasi',
        default='BKI',
        help='Biro klasifikasi yang mensertifikasi kapal, misal: BKI, Lloyd\'s, DNV, BV.',
    )
    class_notation = fields.Char(
        string='Notasi Klas',
        help='Notasi klasifikasi kapal dari BKI, misal: A100 Tug.',
    )
    doc_status_vessel = fields.Selection(
        related='doc_status', string='Status Dokumen Kapal',
        readonly=True,
    )

    # ── Driver license requirement ────────────────────────────────────────────
    required_license_type = fields.Selection(
        REQUIRED_LICENSE_TYPES, string='SIM yang Diperlukan',
        default='A',
        help='Kategori SIM minimum yang diperlukan untuk mengoperasikan kendaraan ini.',
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Compute
    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('vessel_type_id')
    def _compute_is_vessel(self):
        for v in self:
            v.is_vessel = bool(v.vessel_type_id)

    @api.depends(
        'document_ids', 'document_ids.state',
        'document_ids.expiry_date', 'document_ids.doc_type',
    )
    def _compute_document_summary(self):
        for vehicle in self:
            docs = vehicle.document_ids.filtered('active')
            vehicle.document_count = len(docs)

            expired = docs.filtered(lambda d: d.state == 'expired')
            expiring = docs.filtered(lambda d: d.state == 'expiring_soon')

            vehicle.expired_doc_count = len(expired)
            vehicle.expiring_doc_count = len(expiring)

            # Worst-case overall status
            if expired:
                vehicle.doc_status = 'critical'
            elif expiring:
                vehicle.doc_status = 'warning'
            elif docs:
                vehicle.doc_status = 'ok'
            else:
                vehicle.doc_status = 'incomplete'

            # Next expiry
            active_with_date = docs.filtered(lambda d: d.expiry_date and d.state != 'expired')
            if active_with_date:
                soonest = min(active_with_date, key=lambda d: d.expiry_date)
                vehicle.next_expiry_date = soonest.expiry_date
                vehicle.next_expiry_doc = soonest.display_name
            else:
                vehicle.next_expiry_date = False
                vehicle.next_expiry_doc = False

    # ─────────────────────────────────────────────────────────────────────────
    # SIM validation on driver assignment
    # ─────────────────────────────────────────────────────────────────────────

    def _validate_driver_license(self, driver):
        """
        Panggil method ini saat assign driver ke kendaraan.
        Cek apakah driver punya SIM yang sesuai dan masih valid.
        Raise UserError (warning) jika tidak lolos.
        """
        self.ensure_one()
        if not driver or self.required_license_type in (False, 'none'):
            return True

        sim_docs = self.env['fleet.vehicle.document'].search([
            ('driver_id', '=', driver.id),
            ('doc_type', '=', 'sim'),
            ('sim_type', '=', self.required_license_type),
            ('active', '=', True),
        ])

        if not sim_docs:
            raise UserError(_(
                "Peringatan: Pengemudi %(driver)s tidak memiliki %(sim_type)s "
                "yang terdaftar di sistem.\n\n"
                "Kendaraan %(vehicle)s memerlukan %(sim_type)s.\n"
                "Tambahkan dokumen SIM pengemudi terlebih dahulu atau "
                "hubungi GA Manager untuk konfirmasi."
            ) % {
                'driver': driver.name,
                'sim_type': self.required_license_type,
                'vehicle': self.license_plate or self.name,
            })

        valid_sim = sim_docs.filtered(lambda d: d.state == 'valid')
        expiring_sim = sim_docs.filtered(lambda d: d.state == 'expiring_soon')

        if not valid_sim and not expiring_sim:
            raise UserError(_(
                "Peringatan: SIM %(sim_type)s milik %(driver)s sudah EXPIRED "
                "(%(expiry)s).\n\n"
                "Kendaraan %(vehicle)s tidak dapat dioperasikan dengan SIM yang "
                "sudah tidak berlaku. Segera lakukan perpanjangan SIM."
            ) % {
                'driver': driver.name,
                'sim_type': self.required_license_type,
                'expiry': sim_docs[0].expiry_date,
                'vehicle': self.license_plate or self.name,
            })

        if expiring_sim and not valid_sim:
            # Soft warning — tidak raise error, hanya log ke chatter
            self.message_post(body=_(
                "⚠️ Perhatian: SIM %(sim_type)s milik %(driver)s akan expired "
                "dalam %(days)s hari (%(expiry)s). Segera urus perpanjangan."
            ) % {
                'sim_type': self.required_license_type,
                'driver': driver.name,
                'days': expiring_sim[0].days_remaining,
                'expiry': expiring_sim[0].expiry_date,
            })
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # Smart button action
    # ─────────────────────────────────────────────────────────────────────────

    def action_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Dokumen Legal — %s') % (self.license_plate or self.name),
            'res_model': 'fleet.vehicle.document',
            'view_mode': 'list,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {
                'default_vehicle_id': self.id,
                'search_default_vehicle_id': self.id,
            },
        }
