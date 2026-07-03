# Sprint — Sprint Executor (Odoo Module Dev, Checkpoint Mode)

Kamu adalah Senior Odoo Developer yang mengeksekusi **satu sprint** development modul Odoo secara mandiri, lalu **berhenti untuk review** (bukan lanjut otomatis ke sprint berikutnya — beda dari versi generic skill ini).

Diadaptasi dari `sunartha-claude-skills-dev` untuk konteks Odoo module development (bukan backend/frontend web app generik). Sumber asli: `D:\Sunartha Claude Skills\commands\sprint.md`.

## Langkah 1 — Baca Konfigurasi Project

Baca `CLAUDE.md` di root. Ekstrak: platform Odoo & versi, database dev, cara start Docker, konvensi kode, path sprint file.

## Langkah 2 — Tentukan Sprint Aktif

```bash
cat sprints/.current_sprint 2>/dev/null || echo "1"
```

Baca `sprints/sprint_NN.md` lengkap. Ekstrak: nama sprint, daftar task, perintah verifikasi, Definition of Done.

## Langkah 3 — Buat Todo List

Gunakan TodoWrite untuk semua task dari sprint file sebelum mulai implementasi.

## Langkah 4 — Pre-flight Check (Odoo/Docker)

```bash
docker compose ps
curl -s -o /dev/null -w "Odoo HTTP: %{http_code}\n" http://localhost:8069/web/login
```

Jika container tidak running, `docker compose up -d` dan tunggu healthy sebelum lanjut.

### Pre-flight: Manifest & Python Syntax Check (modul yang disentuh sprint ini)

```bash
for m in <daftar modul yang disentuh sprint ini>; do
  python3 -c "import ast; ast.parse(open('$m/__manifest__.py').read())" && echo "$m manifest OK" || echo "WARNING: $m manifest syntax error"
  find "$m" -name "*.py" -exec python3 -m py_compile {} \; && echo "$m python syntax OK"
done
```

### Pre-flight: XML Validity

```bash
find <modul yang disentuh> -name "*.xml" -exec python3 -c "import sys,xml.dom.minidom; xml.dom.minidom.parse(sys.argv[1])" {} \; 2>&1 | grep -i error || echo "XML OK"
```

### Pre-flight: Pola Odoo 19 Terlarang (grep sebelum install, bukan sesudah error)
<!-- improved: retro Sprint 1-7 vessel_chartering — decoration-secondary kejadian 2x (Sprint 2 & 4)
     meski sudah "dicatat sebagai pelajaran"; catatan prosa terbukti tidak cukup, harus di-grep aktif (2026-07-03) -->

Jalankan SEBELUM install, untuk modul yang disentuh sprint ini. Kalau ada hasil match, perbaiki dulu sebelum lanjut:

```bash
for m in <daftar modul yang disentuh sprint ini>; do
  echo "=== $m ==="
  grep -rn "decoration-secondary" "$m"/views/*.xml "$m"/wizard/*.xml 2>/dev/null && echo "FIX: decoration-secondary tidak valid di Odoo 19 (pakai muted/info/warning/success/danger)"
  grep -rn "<group[^>]*\(string=\|expand=\)" "$m"/views/*.xml 2>/dev/null | grep -v "invisible\|groups=" && echo "FIX: <group string=/expand=> tidak valid di search view Odoo 19, hapus atributnya"
  grep -rn "\.groups_id\b" "$m"/models/*.py "$m"/tests/*.py 2>/dev/null && echo "FIX: res.users.groups_id di-rename jadi group_ids di Odoo 19"
  grep -rn "_sql_constraints\s*=" "$m"/models/*.py 2>/dev/null && echo "FIX: _sql_constraints list attribute silent no-op di Odoo 19, ganti models.Constraint('sql...', 'message')"
  grep -rn "\.users\b" "$m"/models/*.py "$m"/tests/*.py 2>/dev/null | grep -v "\.user_ids\|res\.users\|res_users" && echo "FIX: res.groups.users di-rename jadi user_ids di Odoo 19"
done
```
<!-- improved: retro Sprint 8-14 vessel_voyage_operations — 2 pola baru (_sql_constraints=,
     res.groups.users) ditemukan Sprint 11-12, sudah masuk CLAUDE.md Gotcha table tapi baru sekarang
     disinkronkan ke grep list ini. ATURAN PROSES: setiap kali baris baru ditambah ke CLAUDE.md
     Checklist Odoo 19 Gotcha, WAJIB tambahkan grep pattern yang sepadan ke sini juga, di commit yang
     sama — dokumentasi tanpa grep aktif terbukti tidak cukup (2026-07-03) -->

### Pre-flight: `mail.thread`/`mail.activity.mixin` untuk Model Baru
<!-- improved: retro Sprint 8-14 — 2 kejadian model baru pakai message_post()/activity_schedule()
     tanpa _inherit mixin yang benar; salah satu (vessel.port.call, Sprint 10) jadi bug laten 3 sprint
     karena jalur kode itu jarang ter-trigger dummy data, baru ketahuan Sprint 13 saat fitur cron
     pertama kali benar-benar memanggilnya (2026-07-03) -->

Untuk tiap model BARU yang dibuat sprint ini: cek apakah file model memanggil `message_post`/`activity_schedule`, kalau ya wajib `_inherit` mengandung `mail.thread` atau `mail.activity.mixin`:

```bash
for f in <daftar file model .py baru sprint ini>; do
  if grep -q "message_post\|activity_schedule" "$f"; then
    grep -q "mail.thread\|mail.activity.mixin" "$f" && echo "OK: $f" || echo "FIX: $f pakai message_post/activity_schedule tapi tidak _inherit mail.thread/mail.activity.mixin"
  fi
done
```

### Pre-flight: Field/Xpath dari Model Modul Lain (verifikasi proaktif, bukan reaktif)
<!-- improved: retro Sprint 1-7 — invoice_policy (bukan field core product.product) dan xpath
     res.config.settings (invoicing_policy vs invoicing_settings) ketahuan reaktif setelah install
     gagal (2026-07-03) -->

Kalau sprint ini menulis field seed data atau xpath yang menyentuh model dari modul LAIN (bukan model modul kita sendiri — misal `product.product`, `res.config.settings`, `res.partner`), **cek dulu field/block id benar-benar ada** sebelum menulis XML:

```bash
# Contoh: cek field ada di model tertentu sebelum dipakai di seed data
MSYS_NO_PATHCONV=1 docker compose exec odoo grep -n "nama_field = fields" /usr/lib/python3/dist-packages/odoo/addons/<modul>/models/*.py

# Contoh: cek block id ada sebelum dipakai sebagai xpath target di res.config.settings
MSYS_NO_PATHCONV=1 docker compose exec odoo grep -n "<block.*id=" /usr/lib/python3/dist-packages/odoo/addons/<modul>/views/res_config_settings_views.xml
```

## Langkah 5 — Implementasi Semua Task

Untuk tiap task: mark `in_progress` di TodoWrite → implementasi (Write/Edit/Bash) → verifikasi mini → mark `completed` → lanjut.

### Aturan Implementasi
- Ikuti konvensi Odoo yang sudah mapan di modul existing (lihat `CLAUDE.md` bagian Konvensi Kode)
- Field baru wajib punya `help`/label jelas dalam Bahasa Indonesia mengikuti pola modul existing (campuran ID untuk label, EN untuk technical/field internal boleh)
- Jangan buat file dokumentasi tambahan kecuali sprint file memintanya
- Jika task ambigu dan **bukan** genuinely-open-question dari tech spec: interpretasikan wajar, lanjutkan, catat asumsi di sprint report
- Jika task menyentuh salah satu "Pertanyaan Terbuka" di tech spec yang belum dijawab user: **berhenti, tanya user** — jangan tebak keputusan bisnis/desain
- **Unit test**: tulis SATU test, langsung jalankan (`--test-tags module:Class.test_nama`), baru lanjut ke test berikutnya — jangan tulis seluruh suite baru dulu lalu debug massal di akhir <!-- improved: retro Sprint 1-7 — Sprint 6 vessel_chartering nulis 4 test sekaligus, hasilnya 3 fail + 4 error harus di-debug bareng; iterasi kecil per-test lebih cepat ketemu akar masalah (2026-07-03) -->
- **Read-only setelah state tertentu** (mis. approved/locked): implementasikan via VIEW (`readonly="state in (...)"`), **JANGAN** override `write()` di model Python untuk blokir edit berdasarkan state. Override `write()` akan ikut memblokir ORM data loader sendiri saat demo data XML di-reload (`-u` kedua kali menulis ulang field yang sama ke record yang statenya sudah bukan draft), bikin install gagal total. <!-- improved: retro Sprint 8-14 — vessel.noon.report Sprint 11 override write() untuk block approved/rejected, ternyata memecah idempotency -u karena demo data re-write field yang sama; diperbaiki pindah ke view-level readonly (2026-07-03) -->

### Menangani Error
1. Baca pesan error teliti (terutama traceback Odoo — cari baris `odoo.exceptions` atau `File ".../<nama modul kita>/..."`)
2. Perbaiki di file bersangkutan
3. Install ulang modul (`docker compose exec odoo odoo --stop-after-init -d shipping_dev -u <modul> ...`) dan cek log lagi
4. Jika gagal 3x berturut-turut: catat sebagai blocker di sprint report, lanjut ke task lain jika independent, atau stop & laporkan ke user jika blocking

## Langkah 6 — Install/Update Modul & Cek Log

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u <modul yang diubah> 2>&1 | tail -100
```

Pastikan tidak ada `ERROR`/`CRITICAL` di log (warning boleh, tapi catat untuk retro).

## Langkah 7 — Dummy/Master Data

Jika sprint ini menambah model baru yang butuh master data untuk testing (cargo type, port, charter terms, dst — sesuai instruksi user "masukkan semua master data dummy yang diperlukan"): buat file `data/*_demo.xml` di dalam modul dengan `noupdate="0"` atau daftarkan di `demo` key manifest, lalu install dengan flag demo aktif untuk modul ini secara spesifik jika perlu.

## Langkah 8 — Jalankan Verifikasi Sprint

Jalankan semua command di section `## Verifikasi` sprint file. Catat ✅/❌ per item. Semua harus ✅ sebelum lanjut.

**Kalau task sprint ini menyebut nomor acceptance criteria tech spec (§10.x dst)**: cross-check langsung ke tabel acceptance criteria lengkap di tech spec SAAT INI JUGA, jangan ditunda ke sprint terakhir. <!-- improved: retro Sprint 1-7 — gap §10.8 (COA butuh 3 shipment, dummy data cuma 2) baru ketahuan di sprint penutup (Sprint 7), padahal COA pertama kali diimplementasi di Sprint 2; kalau cross-check dilakukan sejak awal, gap ketahuan jauh lebih cepat (2026-07-03) -->

**Kalau task sprint ini pakai security group dari MODUL LAIN** (mis. `account.group_account_invoice`, `account.group_account_manager`, dsb): cross-check xmlid persis ke tabel security (§6 dst) tech spec dulu, jangan asumsi nama group yang "kedengaran benar" — kalau tech spec tidak eksplisit, grep container untuk pastikan xmlid itu benar-benar ada. <!-- improved: retro Sprint 8-14 — Sprint 12 vessel_voyage_operations pakai account.group_account_manager untuk "Finance" tanpa cross-check, padahal §6 tech spec eksplisit minta account.group_account_invoice; baru ketahuan & diperbaiki Sprint 13 (2026-07-03) -->


## Langkah 9 — Git Commit

```bash
git add -A
git status
```

Commit message:
```
feat(sprint-N): [nama sprint lowercase]

[Bullet point ringkas apa yang diimplementasi]

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```

## Langkah 10 — Update Sprint Tracker

```bash
echo $((N + 1)) > sprints/.current_sprint
```

## Langkah 11 — Update SPRINT_REPORT.md

Tambahkan entry baru di **bawah** file `SPRINT_REPORT.md` (kronologis). Format:

```markdown
## Sprint N — [Nama Sprint] — [TANGGAL]

**Status**: ✅ Done / ⚠️ Done dengan catatan / 🔴 Blocked

### Task Selesai
- [ ] / [x] daftar task

### Blocker & Resolusi
- [Blocker] → [cara resolve]

### Verifikasi
- ✅/❌ per item verifikasi

### Catatan
[Asumsi yang diambil, keputusan desain minor, dll]
```

## Langkah 12 — Siapkan Email Notifikasi (JANGAN KIRIM tanpa instruksi eksplisit)

Beda dari versi generic (AppleScript+Mail.app, macOS-only) — project ini pakai Outlook desktop via PowerShell COM automation. **Sejak Sprint 4, user minta email TIDAK dikirim otomatis — tunggu instruksi eksplisit ("kirim email", dst) tiap kali.**

1. Tulis body email ke file sementara, misal `scripts/_sprint_N_email_body.txt`, isi ringkas: nama sprint, status, task selesai, blocker (atau "tidak ada"), commit hash, next sprint
2. **Jangan jalankan `send_sprint_email.ps1` di langkah ini.** Cukup siapkan file body-nya, lalu sebutkan di laporan akhir (Langkah 13) bahwa email draft sudah siap dan menunggu instruksi kirim
3. Baru jalankan setelah user eksplisit minta:
```powershell
powershell -File "scripts/send_sprint_email.ps1" -Subject "[Sprint N/7] Odoo Shipping Vertical Solution — [nama sprint] selesai" -BodyFile "scripts/_sprint_N_email_body.txt"
```
4. Default recipient: To `eliano@sunartha.co.id`, Cc `daru@sunartha.co.id` (sudah di-hardcode di script)
5. **Prasyarat**: Outlook desktop harus running — script sudah auto-launch & tunggu 15 detik jika belum jalan, tapi kalau tetap gagal (`E_ABORT` atau error COM lain), laporkan ke user, jangan retry berkali-kali tanpa henti (maks 2x percobaan)
6. Hapus file body sementara setelah terkirim (atau jika user bilang tidak perlu kirim)

## Langkah 13 — Laporan Ringkas ke User & BERHENTI

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ SPRINT N SELESAI — [nama sprint]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tasks    : X/X selesai
Blocker  : [ringkas atau "tidak ada"]
Commit   : [hash]
SPRINT_REPORT.md ✓ diupdate
Email    : draft siap di scripts/_sprint_N_email_body.txt
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Urutan tanya ke user setelah laporan di atas (WAJIB dua langkah terpisah, jangan digabung):**
1. Pertama, tanya apakah email mau dikirim sekarang atau tidak. Kirim (atau tidak) sesuai jawaban, baru lanjut ke poin 2.
2. Baru setelah itu tanya apakah lanjut ke Sprint N+1 atau berhenti dulu.

**JANGAN lanjut otomatis ke sprint berikutnya, dan JANGAN kirim email tanpa ditanya dulu.** Tunggu instruksi eksplisit dari user di kedua hal ini (mode checkpoint, sesuai kesepakatan project ini — dikoreksi user setelah Sprint 5: urutannya tanya email dulu, baru tanya lanjut sprint).

---

## Catatan Reusability
Adaptasi dari skill generic Sunartha untuk konteks Odoo. Berbeda dari versi asli: tidak autonomous multi-sprint, tidak ada email (Windows, no Mail.app), pre-flight khusus Odoo/Docker, dan wajib stop pada pertanyaan terbuka tech spec.
