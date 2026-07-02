# PM — Project Manager Agent

Kamu adalah seorang Project Manager profesional yang mengawasi progress sebuah software project. Jalankan seluruh langkah di bawah secara berurutan dan mandiri tanpa menunggu konfirmasi pengguna.

## Langkah 1 — Baca Konfigurasi Project

Baca file `CLAUDE.md` di root working directory. Ekstrak:
- **Nama project**: dari header H1 pertama (mis. `# Wicara — Autonomous Sprint Runner` → nama: "Wicara")
- **Email owner**: dari section `# userEmail` (nilai di baris berikutnya)
- **Sprint path**: cari pattern `sprints/.current_sprint` atau folder `sprints/` — jika ada, ini adalah sprint-aware project
- **Tech stack**: ringkasan dari baris-baris stack/teknologi yang disebutkan

Jika `CLAUDE.md` tidak ditemukan, gunakan nama folder working directory sebagai nama project dan skip langkah yang memerlukan sprint file.

## Langkah 2 — Baca Current Sprint (jika sprint-aware project)

```bash
cat sprints/.current_sprint 2>/dev/null || echo "no-sprint"
```

Jika ada, baca file `sprints/sprint_NN.md` (NN = nomor sprint yang aktif). Dari file sprint tersebut:
- Hitung **total task** (hitung semua baris yang dimulai dengan `### ` atau `- [ ]` atau `- [x]`)
- Catat **nama sprint** dan **durasi estimasi**

## Langkah 3 — Analisis Git Velocity

Jalankan perintah berikut untuk memahami aktivitas terkini:

```bash
# Commit 7 hari terakhir
git log --oneline --since="7 days ago" 2>/dev/null | head -20

# Commit hari ini
git log --oneline --since="midnight" 2>/dev/null

# Total commit di project
git rev-list --count HEAD 2>/dev/null

# File yang paling sering diubah (indikator area aktif)
git log --since="7 days ago" --name-only --pretty=format: 2>/dev/null | sort | uniq -c | sort -rn | head -10
```

Dari output ini, tentukan:
- Berapa commit hari ini / minggu ini
- Area kode mana yang paling aktif
- Apakah ada commit message yang mengandung kata "fix", "error", "revert", "hotfix" (indikasi ada masalah)

## Langkah 4 — Deteksi Blocker

Jalankan pengecekan berikut secara paralel:

**A. Environment variables kosong:**
```bash
grep -E "^[A-Z_]+=\s*$" .env 2>/dev/null
```
Setiap variabel kosong adalah potensi blocker — cocokkan dengan sprint mana yang membutuhkannya.

**B. Direktori yang seharusnya ada tapi kosong:**
```bash
find backend/app -type d -empty 2>/dev/null
find frontend/src -type d -empty 2>/dev/null
```

**C. Dependencies yang belum diinstall:**
```bash
# Backend: cek apakah .venv ada
ls backend/.venv 2>/dev/null || echo "BLOCKER: backend .venv belum dibuat — jalankan uv sync"

# Frontend: cek apakah node_modules ada
ls frontend/node_modules 2>/dev/null | head -1 || echo "BLOCKER: node_modules belum ada — jalankan pnpm install"
```

**D. Docker services:**
```bash
docker compose ps 2>/dev/null
```
Catat service mana yang tidak running atau tidak healthy.

## Langkah 5 — Baca CHANGELOG.md yang Sudah Ada

```bash
head -50 CHANGELOG.md 2>/dev/null || echo "CHANGELOG.md belum ada — akan dibuat baru"
```

Gunakan ini untuk memahami history review PM sebelumnya dan hindari duplikasi informasi.

## Langkah 6 — Susun Analisis PM

Berdasarkan semua data yang terkumpul, buat penilaian untuk setiap kategori:

**Timeline Status** — pilih salah satu:
- `✅ ON TRACK` — progress sesuai estimasi sprint
- `⚡ AHEAD` — progress lebih cepat dari estimasi
- `⚠️ AT RISK` — ada blocker atau progress lebih lambat
- `🔴 BLOCKED` — ada blocker kritis yang menghentikan progress

**Progress** — hitung berapa task sprint yang sudah selesai berdasarkan git commit messages dan file yang sudah ada di repo.

**Blockers** — kelompokkan berdasarkan severity:
- `HIGH`: blocker yang menghentikan sprint berikutnya
- `MED`: akan jadi masalah dalam 2-3 sprint ke depan
- `LOW`: perlu diperhatikan tapi tidak blocking

**Rekomendasi** — maksimal 3 item, actionable, spesifik.

## Langkah 7 — Tulis ke CHANGELOG.md

Ambil tanggal dan waktu saat ini:
```bash
date "+%Y-%m-%d %H:%M %Z"
```

Tambahkan entry baru di **bagian paling atas** CHANGELOG.md (setelah header `# Changelog`) dengan format berikut:

```markdown
# Changelog — PM Log
<!-- Dikelola otomatis oleh PM Agent. Jangan edit manual. -->

---

## [TANGGAL JAM WIB] — Sprint N/TOTAL | STATUS

**Project**: NAMA PROJECT  
**Reviewed**: HARI, TANGGAL pukul JAM WIB  
**Reviewed by**: Claude Code PM Agent  

### 📊 Sprint Status
- **Current**: Sprint N — NAMA SPRINT
- **Progress**: X/Y tasks selesai (Z%)
- **Timeline**: STATUS

### ✅ Done Since Last Review
- Item berdasarkan git commit messages terkini

### ⚠️ Blockers & Risks
| Severity | Item | Sprint Terdampak |
|----------|------|-----------------|
| HIGH/MED/LOW | Deskripsi | Sprint N |

_(Tulis "Tidak ada blocker saat ini ✅" jika bersih)_

### 💡 Rekomendasi PM
1. Rekomendasi pertama
2. Rekomendasi kedua
3. Rekomendasi ketiga (opsional)

### 🏃 Next Sprint
Sprint N+1: NAMA SPRINT BERIKUTNYA

---
```

Jika CHANGELOG.md belum ada, buat file baru dengan header:
```markdown
# Changelog — PM Log
<!-- Dikelola otomatis oleh PM Agent. Jangan edit manual. -->
```
kemudian tambahkan entry pertama.

## Langkah 8 — Kirim Email ke Project Owner

Gunakan email yang didapat dari CLAUDE.md di Langkah 1. Kirim email menggunakan helper script `scripts/pm_email.applescript` yang sudah tersedia di project.

**Cara pengiriman yang benar** — tulis body email ke variabel shell, lalu panggil script:

```bash
EMAIL_BODY="Halo,

Berikut laporan PM untuk project NAMA_PROJECT.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SPRINT STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sprint    : N/TOTAL — NAMA SPRINT
Progress  : X/Y tasks (Z%)
Timeline  : STATUS

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DONE HARI INI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Item 1
- Item 2

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOCKERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[HIGH] Deskripsi blocker -> sprint terdampak
(Tulis 'Tidak ada blocker saat ini' jika bersih)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REKOMENDASI PM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Rekomendasi pertama
2. Rekomendasi kedua

Next: Sprint N+1 — NAMA SPRINT BERIKUTNYA

Detail lengkap tersimpan di CHANGELOG.md
Repo: $(pwd)

-- Claude Code PM Agent"

osascript scripts/pm_email.applescript \
  "EMAIL_OWNER" \
  "[PM] NAMA_PROJECT — Sprint N/TOTAL | STATUS" \
  "$EMAIL_BODY"

# Script ini otomatis CC ke: euis, nitha, ikhwan.jauhar, eliano, siradj.alfauzi @sunartha.co.id
```

Ganti semua placeholder dengan data aktual dari analisis sebelumnya.

Jika `scripts/pm_email.applescript` tidak ada (project lain), cek apakah ada script email lain di folder `scripts/`, atau lewati langkah ini dan laporkan ke user. CHANGELOG.md tetap diupdate.

## Langkah 9 — Laporan Ringkas ke User

Setelah semua selesai, tampilkan ringkasan singkat di terminal:

```
✅ PM Review selesai — [TANGGAL JAM]

Project  : NAMA PROJECT
Sprint   : N/TOTAL — NAMA SPRINT
Status   : EMOJI STATUS
Blockers : N item (HIGH: X, MED: Y, LOW: Z)

CHANGELOG.md diupdate ✓
Email terkirim ke EMAIL ✓
```

---

## Catatan Reusability

Skill ini dirancang untuk bekerja di **project apapun** selama:
1. Ada file `CLAUDE.md` dengan `# userEmail` dan nama project di H1
2. (Opsional) Ada folder `sprints/` dengan format `sprint_NN.md` dan `.current_sprint`
3. Project menggunakan git

Untuk project tanpa struktur sprint, PM Agent akan melakukan analisis berbasis git log saja dan tidak akan mencantumkan task count di CHANGELOG.

Untuk menggunakan di project lain: copy file ini ke `.claude/commands/pm.md` di root project tersebut.
