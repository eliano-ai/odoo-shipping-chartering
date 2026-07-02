from odoo import fields, models


class VesselCrewRank(models.Model):
    _name = 'vessel.crew.rank'
    _description = 'Jabatan / Rank ABK Kapal'
    _order = 'sequence, name'

    name = fields.Char(string='Nama Jabatan', required=True, translate=True)
    code = fields.Char(string='Kode', help='Misal: MASTER, CHIEF_OFFICER, KKM, dll')
    sequence = fields.Integer(default=10)
    is_officer = fields.Boolean(
        string='Perwira (Officer)',
        help='Centang untuk jabatan perwira: Nahkoda, Mualim, KKM, Masinis',
    )
    is_watchkeeper = fields.Boolean(
        string='Wajib Jaga (Watchkeeper)',
        help='Jabatan yang memiliki kewajiban jaga navigasi atau mesin',
    )
    department = fields.Selection([
        ('deck', 'Dek (Deck)'),
        ('engine', 'Mesin (Engine)'),
        ('catering', 'Katering / Umum'),
        ('other', 'Lainnya'),
    ], string='Departemen', default='deck', required=True)
    min_rest_hours_per_day = fields.Integer(
        string='Min. Istirahat/Hari (jam)',
        default=10,
        help='STCW VIII/1: minimum 10 jam istirahat per periode 24 jam',
    )
    min_rest_hours_per_week = fields.Integer(
        string='Min. Istirahat/Minggu (jam)',
        default=77,
        help='STCW VIII/1: minimum 77 jam istirahat per periode 7 hari',
    )
    required_coc_grade = fields.Char(
        string='CoC Minimum',
        help='Kelas CoC minimum yang diperlukan untuk jabatan ini. '
             'Misal: ANT-I untuk Nahkoda, ATT-I untuk KKM.',
    )
    description = fields.Text(string='Keterangan')
    active = fields.Boolean(default=True)
    seafarer_count = fields.Integer(
        compute='_compute_seafarer_count', string='Jumlah ABK',
    )

    def _compute_seafarer_count(self):
        for rec in self:
            rec.seafarer_count = self.env['vessel.seafarer'].search_count([
                ('vessel_rank_id', '=', rec.id),
            ])
