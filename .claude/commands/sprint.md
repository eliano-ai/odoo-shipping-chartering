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

## Langkah 5 — Implementasi Semua Task

Untuk tiap task: mark `in_progress` di TodoWrite → implementasi (Write/Edit/Bash) → verifikasi mini → mark `completed` → lanjut.

### Aturan Implementasi
- Ikuti konvensi Odoo yang sudah mapan di modul existing (lihat `CLAUDE.md` bagian Konvensi Kode)
- Field baru wajib punya `help`/label jelas dalam Bahasa Indonesia mengikuti pola modul existing (campuran ID untuk label, EN untuk technical/field internal boleh)
- Jangan buat file dokumentasi tambahan kecuali sprint file memintanya
- Jika task ambigu dan **bukan** genuinely-open-question dari tech spec: interpretasikan wajar, lanjutkan, catat asumsi di sprint report
- Jika task menyentuh salah satu "Pertanyaan Terbuka" di tech spec yang belum dijawab user: **berhenti, tanya user** — jangan tebak keputusan bisnis/desain

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
