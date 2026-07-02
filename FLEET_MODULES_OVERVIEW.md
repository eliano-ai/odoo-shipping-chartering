# Breakdown Modul Fleet — Menu, Fitur & Tujuan

Dokumen ini merangkum 5 modul custom Odoo yang berfokus pada manajemen armada (kendaraan darat & kapal laut) di repo `odoo-shipping`. Untuk tiap modul dijelaskan lokasi menu, breakdown fitur, dan tujuan/fungsi bisnis dari masing-masing fitur.

---

## 1. `fleet_document_id` — Dokumen Legal

**Menu:** Fleet → **Dokumen Legal**
**Depends:** `fleet`, `hr`, `account`, `mail`, `hr_expense`

- **Semua Dokumen** — `fleet.vehicle.document`
  - Master tipe dokumen dari `fleet.document.type`: STNK, BPKB, KIR, SIM, Asuransi, Emisi, Dispensasi (darat) + BKI, Sijil, STCW, Buku Pelaut (kapal)
    → *Tujuan: satu sistem menangani armada darat & laut tanpa duplikasi model; filter otomatis sesuai tipe kapal*
  - Field khusus darat: kategori SIM (A/A Umum/B1/B1 Umum/B2/B2 Umum/C/D) + Pengemudi
    → *Tujuan: cegah pelanggaran hukum (sopir >3.5 ton pakai SIM biasa) yang jadi tanggung jawab perusahaan*
  - Field khusus kapal: ABK/Crew + Jabatan/Rank (Nahkoda, KKM, Mualim I, dst)
    → *Tujuan: dokumen laut (Sijil, STCW) melekat ke individu ABK, bukan ke kendaraan*
  - **Status otomatis**: Valid / Segera Expired / Expired / Tidak Ada (`expiry_date` vs `alert_threshold_days`, default 30 hari)
    → *Tujuan: cegah kendaraan/kapal beroperasi dengan dokumen mati — biasanya baru ketahuan saat razia/inspeksi*
  - **Intermediate Survey** — auto-hitung `next_survey_date` dari interval bulan di master (untuk sertifikat BKI)
    → *Tujuan: BKI berlaku 5 tahun tapi wajib disurvey tiap tahun; tanpa ini sertifikat bisa dianggap valid padahal survey tahunan terlewat, berisiko dibatalkan class society*
  - Upload lampiran multi-file, biaya perpanjangan terakhir (Monetary)
    → *Tujuan: bukti dokumen tersimpan digital, tidak bergantung arsip fisik*
  - Tombol **Perpanjang Dokumen** → buka wizard
- **Dashboard Compliance** — list `fleet.vehicle` dikelompokkan status dokumen (OK/Warning/Critical/Incomplete)
  → *Tujuan: Fleet Manager lihat kondisi compliance seluruh armada dalam 1 layar, dasar prioritas mana yang segera diurus*
- **Riwayat Perpanjangan** *(Fleet Manager only)* — log semua histori perpanjangan
  → *Tujuan: bukti historis untuk audit internal/eksternal (biaya & frekuensi perpanjangan)*
- **Konfigurasi** *(Fleet Manager only)*
  - **Master Tipe Dokumen** — kategori, terkait crew/pengemudi, default alert days, interval survey, berlaku tipe kapal tertentu
    → *Tujuan: admin atur aturan sekali di master, otomatis berlaku ke semua record dokumen*
  - **Master Tipe Kapal** — Tug, Barge, Cargo/Bulk Carrier, Tanker, Passenger, Ferry, Supply/OSV, Umum
    → *Tujuan: dasar filter dokumen relevan per jenis kapal (sertifikat tanker beda dari kapal penumpang)*

**Wizard Perpanjangan Dokumen** — tanggal perpanjangan, expired baru, no. dokumen baru (opsional), biaya, opsi buat HR Expense otomatis, upload scan baru
→ *Tujuan: standarisasi proses perpanjangan sekaligus catat biaya administrasi ke expense karyawan yang mengurus*

**Otomatis (cron harian)** — alert email H-30/H-7/H-0/H+7 sebelum & sesudah expired
→ *Tujuan: pengingat bertingkat supaya ada cukup waktu urus dokumen sebelum kendaraan/kapal "grounded"*

**Laporan:** PDF Compliance Summary

---

## 2. `fleet_fuel_log` — Fuel

**Menu:** Fleet → **Fuel** *(akses: Fleet Manager & Driver)*
**Depends:** `fleet`, `stock`, `account`, `mail`, `uom`

- **Fuel Logs** — `fleet.fuel.log`
  - 3 tipe transaksi: Refueling (SPBU/Bunker), Daily Consumption, Per Trip/Voyage
    → *Tujuan: BBM darat dicatat per isi ulang, BBM kapal (MFO) per jam mesin/voyage — satu model fleksibel untuk 2 pola tanpa modul terpisah*
  - Odometer start/end → auto-hitung distance & **consumption rate** (L/100km); untuk kapal: engine hours + consumption per hour manual
    → *Tujuan: ukuran efisiensi standar untuk bandingkan performa antar kendaraan/kapal & deteksi mesin bermasalah*
  - **Deteksi anomali otomatis** — bandingkan consumption terhadap rata-rata historis (threshold % dari master fuel type) → auto email Fleet Manager
    → *Tujuan: anti-kecurangan/kebocoran BBM — fraud (solar "dijual" sebagian) biasanya baru ketahuan lewat laporan bulanan; deteksi real-time mencegat kerugian lebih cepat*
  - Workflow **Draft → To Approve → Approved → Posted**
    → *Tujuan: kontrol internal — entry sopir/ABK tidak langsung jadi biaya resmi tanpa direview Fleet Manager*
  - Approved → auto buat `stock.move` konsumsi BBM
    → *Tujuan: BBM adalah barang persediaan, konsumsinya harus mengurangi stok Inventory secara akurat*
  - Posted → auto buat `account.move` (journal entry biaya BBM)
    → *Tujuan: biaya BBM otomatis masuk pembukuan, hindari selisih laporan operasional vs finance*
  - Smart button lihat Stock Move & Journal Entry terkait
- **Pending Approval** *(Fleet Manager only)* — filter log status "To Approve"
  → *Tujuan: antrian kerja Fleet Manager terpisah dari noise log lain*
- **My Logs** *(Driver only)* — log milik user sendiri
  → *Tujuan: driver/ABK hanya lihat & input miliknya sendiri, UI lebih sederhana*
- **Trips / Voyages** — `fleet.vehicle.trip`
  - Jadwal keberangkatan-kedatangan, pelabuhan asal-tujuan, agregasi semua fuel log (total qty, cost, avg consumption)
    → *Tujuan: biaya & efisiensi BBM kapal lebih bermakna per perjalanan — dasar hitung biaya operasional per rute/charter*
  - Workflow Planned → Ongoing → Done/Cancelled
- **Fuel Types** *(Fleet Manager only)* — master BBM, harga default, produk Inventory, akun biaya, threshold anomali %
  → *Tujuan: satu sumber kebenaran harga & akun akuntansi per jenis BBM*

**Laporan:** pivot cost, grafik trend, perbandingan antar kendaraan

---

## 3. `fleet_maintenance_schedule` — Maintenance

**Menu:** Fleet → **Maintenance** *(akses: Fleet Manager & Technician)*
**Depends:** `fleet`, `maintenance`, `stock`, `mail`

- **Schedules** — `fleet.maintenance.schedule`
  - 4 tipe: Preventive, Corrective, Predictive, Overhaul
    → *Tujuan: klasifikasi standar industri untuk analisa biaya & planning budget tahunan*
  - Trigger basis: Date / Odometer-Engine Hours / Keduanya
    → *Tujuan: mencerminkan praktik nyata bengkel (misal ganti oli tiap 6 bulan ATAU 5000 km, mana lebih dulu tercapai)*
  - Assign Technician + Fleet Manager, estimasi biaya vs biaya aktual (auto dari spare parts)
    → *Tujuan: evaluasi akurasi budgeting & dasar negosiasi vendor spare part*
  - Line item **Spare Parts** (`fleet.maintenance.part`) — qty planned/used, unit cost, subtotal otomatis
  - Workflow **Draft → Confirmed** (auto-create `maintenance.request` + reminder activity) **→ In Progress → Done** (consume spare parts via `stock.picking`)
    → *Tujuan: terhubung ke modul maintenance standar Odoo (satu sistem tracking, bukan dua); konsumsi part otomatis kurangi stok gudang mencegah selisih fisik vs sistem*
  - Smart button lihat Maintenance Request & Stock Picking terkait
  - **Reminder email otomatis** (cron, H-berapa hari sebelum scheduled date)
    → *Tujuan: mencegah jadwal maintenance yang dibuat berbulan-bulan lalu terlewat, berisiko breakdown di tengah operasi*
- **My Assignments** *(Technician only)* — list/form/**calendar** jadwal milik teknisi sendiri
  → *Tujuan: teknisi lihat beban kerja pribadi dalam format kalender, memudahkan penjadwalan harian*

---

## 4. `fleet_model_sparepart` — Spareparts

**Menu:** Fleet → **Spareparts** *(akses: Fleet Sparepart Manager)*
**Depends:** `fleet`, `stock`

- Tab **Sparepart** di form `fleet.vehicle.model`
  - Lookup produk terbatas kategori **"Vessel Inventory"** (auto-seed kategori ini)
    → *Tujuan: sparepart kapal jumlahnya banyak & spesifik per model — filter kategori cegah salah pilih produk dari kategori Inventory lain*
  - Auto-populate dari produk: part number, vendor utama, unit cost, UoM (bisa di-override)
    → *Tujuan: konsistensi data — spesifikasi teknis satu sumber kebenaran (master produk), tidak diketik ulang manual (rawan typo/beda harga)*
  - **Qty On-Hand** real-time dari `stock.quant`
    → *Tujuan: cek ketersediaan stok cepat tanpa buka modul Inventory terpisah, penting saat kapal akan berlayar*
  - **Qty Allocated** (manual) & **Qty Difference** (on-hand − allocated)
    → *Tujuan: bedakan stok gudang total vs yang sudah "dijatah" untuk kapal tertentu; nilai negatif jadi sinyal perlu re-order*
  - Constraint 1 produk per kendaraan (no duplicate)
    → *Tujuan: cegah data ganda/tercecer saat rekap*

---

## 5. `vessel_crew_management` — Crew Management

> *(baru, belum di-commit ke git)*

**Menu:** Fleet → **Crew Management**
**Depends:** `fleet`, `hr`, `hr_payroll`, `mail`, `calendar`, `fleet_document_id` (pakai model dokumen dari modul dokumen legal untuk sertifikat ABK)

- **Penugasan ABK** — `vessel.crew.assignment`, jantung modul ini (sign on/off)
  - Assign ABK ke kapal (`is_vessel=True`) dengan jabatan spesifik untuk penugasan itu
  - Jadwal tanggal & pelabuhan sign on/off rencana vs aktual, alasan sign off (kontrak, medis, pribadi, darurat, PHK, repatriasi, lainnya)
  - Auto-hitung durasi kontrak & hari aktual di laut
  - **Validasi sertifikat STCW otomatis** saat konfirmasi — blokir jika ada cert expired, warning jika akan expired selama masa tugas
    → *Tujuan: kontrol kepatuhan hukum paling kritis — kirim ABK dengan CoC/Buku Pelaut expired melanggar STCW 1978, berisiko kapal ditahan Port State Control atau didenda; blokir otomatis mencegah human error*
  - Cegah double-assignment (1 ABK tidak bisa dapat 2 penugasan aktif bersamaan)
    → *Tujuan: ABK secara fisik tak bisa bertugas di 2 kapal sekaligus — cegah kesalahan input yang baru ketahuan saat jadwal sudah berjalan*
  - Workflow **Draft → Confirmed** (validasi cert + kirim notifikasi) **→ On Board** (sign on aktual) **→ Completed** (via wizard sign off) **/ Cancelled**
  - **Notifikasi otomatis** via Email dan/atau WhatsApp (pilihan channel per assignment): jadwal sign on, reminder H-3 (cron), konfirmasi sign on/off — WA lewat modul native Odoo atau fallback gateway HTTP eksternal (Fonnte/Wablas dll, dikonfigurasi via System Parameters)
    → *Tujuan: ABK sering di lokasi dengan akses email terbatas tapi WhatsApp selalu dipakai — dual channel memastikan info benar-benar sampai*
  - Log semua notifikasi terkirim/gagal (`vessel.notification.log`)
    → *Tujuan: audit trail — bukti notifikasi sudah/belum sampai jika ada dispute*
  - Auto-update status ABK di manning pool (available/standby/on_board) mengikuti state
  - Wizard **Sign Off** — tanggal, pelabuhan, alasan, preview total hari di laut → generate Sea Service Log
  - Cron **Reminder H-3** sebelum sign on
    → *Tujuan: kurangi risiko ABK tidak siap/absen saat kapal harus berangkat — telat berlayar karena kru belum lengkap adalah kerugian operasional besar (demurrage, kontrak charter)*
  - Cron **Overdue Sign On** — flag assignment yang lewat tanggal sign on tanpa konfirmasi
    → *Tujuan: deteksi dini beri waktu operasional cari pengganti sebelum jadwal keberangkatan terganggu*
- **Daftar ABK** — `vessel.seafarer` (extend `hr.employee`, 1 employee = 1 record)
  - Data pelaut: No. Buku Pelaut + expiry, No. & kelas CoC/ATKAPAL (ANT I-V, ATT I-V, BST) + expiry, Seaman Book internasional
    → *Tujuan: field khusus maritim yang tidak ada di HR standar, tapi tetap terhubung ke payroll & absensi lewat extend, bukan model baru total*
  - **Manning Pool Status**: Tersedia / Di Kapal / Cuti / Pelatihan / Cuti Medis / Standby / Tidak Aktif
    → *Tujuan: tahu real-time siapa ABK available untuk ditugaskan — dasar keputusan cepat saat kapal butuh kru mendadak*
  - Smart info: penugasan aktif & kapal saat ini, total hari di laut akumulasi, jumlah cert akan/sudah expired
  - Sertifikat & dokumen ditarik dari `fleet.vehicle.document` (modul `fleet_document_id`) berkategori vessel
- **Jadwal Rotasi** — `vessel.crew.schedule` (planning tool, terpisah dari assignment aktual)
  - Tipe jadwal On Board / Cuti / Pelatihan / Standby per ABK-kapal-rentang tanggal
  - Integrasi **Calendar Odoo** — auto-create `calendar.event` saat dikonfirmasi
    → *Tujuan: planning kru jangka panjang butuh visual kalender; sinkron ke Calendar Odoo supaya reminder muncul di kalender pribadi user*
  - Tombol "Buat Assignment" — generate `vessel.crew.assignment` langsung dari jadwal
- **Konfigurasi → Master Jabatan ABK** — `vessel.crew.rank`
  - Departemen Dek/Mesin/Katering/Lainnya, flag Officer & Watchkeeper
  - Batas istirahat STCW VIII/1 (default 10 jam/hari, 77 jam/minggu), CoC minimum per jabatan
    → *Tujuan: referensi kepatuhan regulasi jam kerja/istirahat yang diaudit otoritas pelayaran, terutama untuk watchkeeper (jaga navigasi/mesin) yang risiko kelelahannya tinggi*
- **Extend `fleet.vehicle`** — ABK aktif di kapal (manning list real-time), jumlah crew, riwayat penugasan, jadwal crew
  → *Tujuan: kapten/operasional darat tahu siapa saja sedang di atas kapal tanpa query manual — penting untuk keadaan darurat (evakuasi, SAR) & pelaporan ke otoritas pelabuhan*

**Sea Service Log** (`vessel.sea.service.log`) — dibuat otomatis saat sign off (kapal, jabatan, tanggal, pelabuhan, GT & bendera kapal)
→ *Tujuan: bukti resmi jumlah hari berlayar (sea time) untuk kenaikan pangkat/perpanjangan CoC sesuai standar STCW, tanpa rekap manual yang rawan salah/hilang*

---

## Benang Merah Lintas Modul

Kelima modul ini dibangun untuk menjembatani 2 dunia dalam Odoo `fleet` — kendaraan darat & kapal laut — sambil memenuhi kepatuhan regulasi Indonesia (Dishub, Ditjen Hubla, STCW/MLC internasional) yang tidak ada di modul fleet standar, plus menutup celah kontrol internal (fraud BBM, dokumen expired, sertifikat kadaluarsa) yang secara finansial dan legal berisiko tinggi bagi perusahaan pelayaran/logistik.

Pola umum yang dipakai di semua modul:
- Semua model transaksional pakai `mail.thread` / `mail.activity.mixin` untuk chatter, tracking field, dan activity/reminder
- Workflow state machine dengan tombol aksi eksplisit (bukan langsung edit status)
- Integrasi otomatis ke Inventory (`stock.move` / `stock.picking`) dan Accounting (`account.move`) saat status tertentu tercapai
- Cron job harian untuk notifikasi proaktif (expiry, anomali, reminder)
