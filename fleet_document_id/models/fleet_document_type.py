from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


DOCUMENT_CATEGORY = [
    ('land', 'Kendaraan Darat'),
    ('vessel', 'Kapal Laut'),
    ('both', 'Keduanya'),
]

VESSEL_TYPE_SELECTION = [
    ('tug', 'Kapal Tunda (Tug)'),
    ('barge', 'Tongkang (Barge)'),
    ('cargo', 'Kapal Kargo / Bulk Carrier'),
    ('tanker', 'Kapal Tanker'),
    ('passenger', 'Kapal Penumpang'),
    ('ferry', 'Kapal Feri'),
    ('supply', 'Kapal Suplai / OSV'),
    ('general', 'Umum (Semua Kapal)'),
]


class FleetDocumentType(models.Model):
    _name = 'fleet.document.type'
    _description = 'Tipe Dokumen Kendaraan / Kapal'
    _order = 'category, sequence, name'
    _rec_name = 'name'

    name = fields.Char(
        string='Nama Dokumen',
        required=True, translate=True,
    )
    code = fields.Char(
        string='Kode',
        help='Kode singkat unik, misal: STNK, BKI_LAMBUNG, SIJIL, dll',
    )
    category = fields.Selection(
        DOCUMENT_CATEGORY, string='Kategori',
        required=True, default='land',
        help='Tentukan apakah dokumen ini untuk kendaraan darat, kapal laut, atau keduanya.',
    )
    sequence = fields.Integer(default=10)
    applicable_vessel_types = fields.Many2many(
        'fleet.document.vessel.type',
        'doc_type_vessel_type_rel',
        'doc_type_id', 'vessel_type_id',
        string='Berlaku untuk Tipe Kapal',
        help='Kosongkan = berlaku untuk semua tipe kapal. '
             'Isi jika dokumen ini hanya relevan untuk tipe kapal tertentu.',
    )
    requires_crew = fields.Boolean(
        string='Terkait ABK / Crew',
        default=False,
        help='Centang jika dokumen ini melekat pada individu ABK '
             '(misal: Sijil, Sertifikat STCW, Buku Pelaut).',
    )
    requires_driver = fields.Boolean(
        string='Terkait Pengemudi',
        default=False,
        help='Centang jika dokumen ini melekat pada pengemudi '
             '(misal: SIM). Hanya berlaku untuk kategori Darat.',
    )
    default_alert_days = fields.Integer(
        string='Default Alert (hari sebelum expired)',
        default=30,
        help='Berapa hari sebelum expired sistem mulai mengirim notifikasi. '
             'Bisa di-override di setiap record dokumen.',
    )
    has_survey_interval = fields.Boolean(
        string='Ada Intermediate Survey',
        default=False,
        help='Aktifkan jika dokumen ini memerlukan survey antara '
             '(misal: sertifikat BKI yang disurvey setiap tahun meski masa berlaku 5 tahun).',
    )
    survey_interval_months = fields.Integer(
        string='Interval Survey (bulan)',
        default=12,
        help='Setiap berapa bulan intermediate survey dilakukan.',
    )
    description = fields.Text(string='Keterangan')
    active = fields.Boolean(default=True)
    document_count = fields.Integer(
        compute='_compute_document_count', string='Jumlah Dokumen',
    )

    @api.depends()
    def _compute_document_count(self):
        for rec in self:
            rec.document_count = self.env['fleet.vehicle.document'].search_count([
                ('doc_type_id', '=', rec.id),
            ])

    @api.constrains('category', 'requires_driver')
    def _check_driver_category(self):
        for rec in self:
            if rec.requires_driver and rec.category == 'vessel':
                raise ValidationError(_(
                    "Dokumen dengan kategori 'Kapal Laut' tidak bisa "
                    "sekaligus membutuhkan Pengemudi. "
                    "Gunakan field 'Terkait ABK' untuk dokumen crew kapal."
                ))

    @api.constrains('category', 'requires_crew')
    def _check_crew_category(self):
        for rec in self:
            if rec.requires_crew and rec.category == 'land':
                raise ValidationError(_(
                    "Dokumen dengan kategori 'Kendaraan Darat' tidak bisa "
                    "sekaligus membutuhkan ABK / Crew."
                ))

    def action_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Dokumen — %s') % self.name,
            'res_model': 'fleet.vehicle.document',
            'view_mode': 'list,form',
            'domain': [('doc_type_id', '=', self.id)],
        }


class FleetDocumentVesselType(models.Model):
    _name = 'fleet.document.vessel.type'
    _description = 'Tipe Kapal'
    _order = 'sequence, name'

    name = fields.Char(string='Nama Tipe Kapal', required=True)
    code = fields.Char(string='Kode')
    sequence = fields.Integer(default=10)
    description = fields.Text(string='Keterangan')
    active = fields.Boolean(default=True)
    vehicle_count = fields.Integer(
        compute='_compute_vehicle_count', string='Jumlah Kapal',
    )

    @api.depends()
    def _compute_vehicle_count(self):
        for rec in self:
            rec.vehicle_count = self.env['fleet.vehicle'].search_count([
                ('vessel_type_id', '=', rec.id),
            ])
            
    def action_view_vehicles(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Kapal — %s') % self.name,
            'res_model': 'fleet.vehicle',
            'view_mode': 'list,form',
            'domain': [('vessel_type_id', '=', self.id)],
        }
