# Retro — Sprint Retrospective (Odoo Module Dev)

Kamu adalah Engineering Lead yang melakukan retrospektif setelah sprint (atau sekelompok sprint) selesai. Tugasmu **mendeteksi pola**, bukan cuma melaporkan apa yang terjadi. Jalankan semua langkah berurutan tanpa menunggu konfirmasi.

Diadaptasi dari `sunartha-claude-skills-dev` (`D:\Sunartha Claude Skills\commands\retro.md`) untuk konteks Odoo module dev — sumber laporan sprint pakai `SPRINT_REPORT.md` (bukan `CHANGELOG.md` dari `/pm`), dan tanpa email (Windows, no Mail.app).

## Langkah 1 — Baca Konfigurasi Project

Baca `CLAUDE.md`. Catat modul yang sedang dikembangkan, path `sprints/`.

## Langkah 2 — Kumpulkan Data Sprint

```bash
cat sprints/.current_sprint 2>/dev/null || echo "unknown"
ls sprints/sprint_*.md 2>/dev/null | sort
```

Untuk tiap sprint file: nama sprint, jumlah task, ada/tidaknya section Verifikasi & Definition of Done.

## Langkah 3 — Analisis Git Log

```bash
git log --oneline
git log --oneline --all | grep -iE "(fix|revert|hotfix|patch|repair|workaround|typo|oops|wrong|broken|error)" || echo "Tidak ada commit masalah"
git log --oneline | grep -E "feat\(sprint-[0-9]+\)" | head -20
git log --name-only --pretty=format: | sort | uniq -c | sort -rn | head -15
```

## Langkah 4 — Analisis SPRINT_REPORT.md

Baca `SPRINT_REPORT.md` lengkap. Untuk tiap entry sprint, ekstrak:

**A. Semua blocker yang pernah muncul** (section "Blocker & Resolusi" tiap entry)

**B. Frekuensi tiap blocker** — blocker yang muncul >1 kali = pola sistemik, bukan kebetulan (contoh nyata dari project ini: dependency Enterprise-only `hr_payroll` di `vessel_crew_management` yang ketahuan saat install pertama kali — cek apakah tipe masalah serupa/dependency issue lain muncul lagi)

**C. Sprint dengan status ⚠️/🔴** di entry

## Langkah 5 — Audit Command Files

```bash
ls .claude/commands/*.md 2>/dev/null
```

Untuk tiap command (`sprint.md`, `retro.md`): apa yang dicek, apa yang **tidak** dicek (gap), apakah ada pola dari `SPRINT_REPORT.md` yang seharusnya sudah di-handle pre-flight tapi belum.

## Langkah 6 — Baca/Buat learning_log.json

```bash
cat learning_log.json 2>/dev/null || echo "{}"
```

Format sama seperti versi generic (lihat `D:\Sunartha Claude Skills\commands\retro.md` §Langkah 6), field `blockers_count` dsb diambil dari `SPRINT_REPORT.md`, bukan `CHANGELOG.md`.

## Langkah 7 — Susun Temuan

Kategori: (A) Pola Blocker Sistemik, (B) Pola Git Bermasalah (commit fix/revert), (C) Gap Command Coverage, (D) Yang Berjalan Baik, (E) Kandidat Perbaikan Command (prioritized HIGH/MED/LOW).

## Langkah 8 — Tulis RETRO.md

Buat/update `RETRO.md` di root, entry baru di **atas** entry lama. Format sama seperti template asli (lihat sumber), ganti referensi `CHANGELOG.md` → `SPRINT_REPORT.md`, dan target perbaikan → `.claude/commands/sprint.md` / `retro.md` / kode modul itu sendiri (bukan hanya command file — untuk Odoo dev, temuan bisa juga berarti "tambah field X ke checklist audit Odoo 19 di CLAUDE.md").

## Langkah 9 — Update learning_log.json

```bash
python3 -c "import json; json.load(open('learning_log.json')); print('JSON valid')"
```

## Langkah 10 — Laporan ke User (tanpa email)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 RETROSPEKTIF SELESAI — [TANGGAL]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sprint dianalisis : N
Recurring blockers: N item
Fix commits       : N
Gap coverage      : N
Kandidat perbaikan: N (HIGH: X, MED: Y, LOW: Z)

RETRO.md          ✓ diupdate
learning_log.json ✓ diupdate
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Catatan Reusability
Bekerja selama ada: `CLAUDE.md`, git, `SPRINT_REPORT.md` (pengganti `CHANGELOG.md`), folder `sprints/` (opsional).
