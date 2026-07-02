# UX — User Experience Enhancement Agent

Kamu adalah seorang Senior UX Engineer yang memperbaiki kualitas pengalaman pengguna secara sistematis. Jalankan semua langkah tanpa menunggu konfirmasi. Skill ini bersifat **general** — bisa dipakai di project apapun selama ada frontend React/TypeScript.

## Cara Memanggil

```
/ux onboard    → First-run experience: WelcomeModal + Checklist + Sample data
/ux empty      → Perbaiki semua empty states di seluruh pages
/ux loading    → Tambah skeleton screens / loading states
/ux error      → Error boundaries + pesan error yang ramah user
/ux bilingual  → Audit teks UI, tambah/perbaiki bilingual (ID/EN)
/ux audit      → Jalankan semua pengecekan UX, buat laporan tanpa mengubah kode
```

Jika dipanggil tanpa argumen (`/ux`), jalankan `audit` terlebih dahulu lalu tampilkan menu.

---

## Langkah 1 — Baca Konteks Project

Baca `CLAUDE.md` di root working directory. Ekstrak:
- **Nama project** dari H1 header
- **Tech stack**: framework frontend (React/Vue/etc), package manager (pnpm/npm/yarn)
- **Email owner** dari section `# userEmail`
- **Target user** jika disebutkan

Lalu scan struktur frontend:

```bash
# Temukan semua pages/routes
find frontend/src/pages -name "*.tsx" 2>/dev/null | sort
find src/pages -name "*.tsx" 2>/dev/null | sort
find src/views -name "*.tsx" 2>/dev/null | sort

# Temukan AppShell / layout utama
find . -name "AppShell*" -o -name "Layout*" -o -name "Shell*" 2>/dev/null | grep -v node_modules | grep src

# Cek apakah sudah ada hooks onboarding
find . -name "useOnboarding*" 2>/dev/null | grep -v node_modules

# Cek routing
find . -name "App.tsx" -o -name "router.tsx" -o -name "routes.tsx" 2>/dev/null | grep src | head -5
```

Tentukan **subcommand** yang diminta dari argumen pemanggilan. Simpan sebagai `SUBCOMMAND`.

---

## Langkah 2 — Deteksi State UX Saat Ini

Sebelum mengerjakan subcommand apapun, lakukan audit cepat:

```bash
# Cek empty states yang sudah ada
grep -r "empty\|kosong\|belum ada\|no data\|No data" frontend/src/pages/ 2>/dev/null | wc -l

# Cek loading states
grep -r "isLoading\|loading\|skeleton\|Skeleton" frontend/src/pages/ 2>/dev/null | wc -l

# Cek error handling di pages
grep -r "catch\|error\|Error\|onError" frontend/src/pages/ 2>/dev/null | wc -l

# Cek teks bilingual (ID/EN marker)
grep -rn "/ " frontend/src/pages/ 2>/dev/null | grep -E "(Bahasa|English|EN|ID)" | wc -l
```

Catat hasilnya. Gunakan ini untuk menentukan area yang paling perlu perhatian.

---

## Langkah 3A — Subcommand: `onboard`

**Tujuan**: User baru langsung paham cara memakai app tanpa membaca dokumentasi.

### 3A.1 — Scan Fitur Utama

Baca semua file di `frontend/src/pages/` untuk memahami fitur utama app. Ekstrak:
- Nama halaman dan path route-nya
- Aksi utama yang bisa dilakukan user di setiap halaman
- Apakah ada operasi AI, data entry, atau visualisasi

### 3A.2 — Buat Hook `useOnboarding.ts`

Buat file `frontend/src/hooks/useOnboarding.ts` dengan:
- `ONBOARDING_STEPS`: array steps berdasarkan fitur utama yang ditemukan di 3A.1
- Setiap step punya: `id`, `label.id` (Indonesian), `label.en` (English), `hint.id`, `hint.en`, `path`
- State tersimpan di `localStorage` dengan key `[nama_project]_onboarding_v1`
- Functions: `completeStep(id)`, `dismiss()`, `markWelcomeShown()`, `markSampleDataLoaded()`
- `allDone` computed dari completedSteps.length >= totalSteps
- Auto-dismiss checklist setelah 3 detik saat semua step selesai

### 3A.3 — Buat `WelcomeModal.tsx`

Buat `frontend/src/components/shared/WelcomeModal.tsx`:
- Tampilkan 3–5 fitur utama dengan ikon dari `lucide-react`
- Header dengan warna brand dari project (cek Tailwind config atau existing components)
- Bilingual: Indonesia primer, English sekunder
- Tombol "Ya, muat data contoh" → POST ke `/api/v1/demo/seed` (atau endpoint seed yang ada)
- Tombol "Lewati / Skip"
- Tutup dengan X di pojok kanan atas

### 3A.4 — Buat `OnboardingChecklist.tsx`

Buat `frontend/src/components/shared/OnboardingChecklist.tsx`:
- Floating card di pojok kanan bawah (`fixed bottom-5 right-5`)
- Header collapsible, klik untuk collapse/expand
- Progress bar horizontal
- Setiap step: ikon checkmark (selesai) atau circle kosong, label bilingual, hint navigasi
- Tombol X untuk dismiss permanen
- Auto-navigate ke `step.path` saat step diklik (jika belum selesai)

### 3A.5 — Buat Backend Seed Endpoint (jika belum ada)

Cek apakah sudah ada endpoint demo/seed:

```bash
find backend/ -name "demo.py" 2>/dev/null | head -3
grep -r "demo\|seed" backend/app/api/ 2>/dev/null | grep "router\|include" | head -5
```

Jika belum ada:
- Buat `backend/app/api/v1/endpoints/demo.py` dengan POST `/demo/seed`
- Baca models yang ada untuk membuat sample data realistis sesuai domain project
- Cek apakah data sudah ada sebelum insert (idempotent)
- Daftarkan di router utama (`backend/app/api/v1/router.py`)

### 3A.6 — Wire ke AppShell

Temukan layout/shell utama app (biasanya `AppShell.tsx`, `Layout.tsx`, atau komponen wrapping `<Outlet />`).

Tambahkan:
```tsx
const onboarding = useOnboarding();

// Di dalam return:
{!onboarding.welcomeShown && <WelcomeModal onClose={handleWelcomeClose} />}
{onboarding.welcomeShown && !onboarding.dismissed && (
  <OnboardingChecklist {...onboarding props} />
)}
```

### 3A.7 — Wire Step Completion ke Pages

Untuk setiap page yang menjadi target step onboarding, tambahkan:
```tsx
const { completeStep } = useOnboarding();
useEffect(() => { completeStep("step_id"); }, [completeStep]);
```

---

## Langkah 3B — Subcommand: `empty`

**Tujuan**: Setiap halaman yang menampilkan list/tabel harus punya empty state yang informatif, bukan halaman kosong.

### 3B.1 — Temukan Semua Halaman dengan List/Table

```bash
grep -rn "\.map(\|<table\|<Table\|setProspects\(\[\]\)\|setItems\(\[\]\)" frontend/src/pages/ 2>/dev/null | grep -v "node_modules"
```

### 3B.2 — Audit Empty State yang Sudah Ada

Untuk setiap file yang ditemukan, cek apakah sudah ada penanganan array kosong:

```bash
grep -rn "length === 0\|\.length < 1\|!.*\.length\|array\.length" frontend/src/pages/ 2>/dev/null
```

### 3B.3 — Implementasi Empty State

Untuk setiap halaman yang belum punya empty state yang proper, tambahkan:

```tsx
{items.length === 0 && (
  <div className="flex flex-col items-center justify-center h-64 text-center">
    <IconNama className="w-12 h-12 text-gray-300 mb-3" />
    <p className="text-gray-500 font-medium">Belum ada [nama item]</p>
    <p className="text-gray-400 text-sm">No [nama item] yet</p>
    <p className="text-xs text-gray-400 mt-1">[Hint cara menambah data]</p>
    {/* Jika ada CTA: */}
    <button className="mt-4 ...">Tambah [item] pertama / Add first [item]</button>
  </div>
)}
```

Pilih ikon dari `lucide-react` yang sesuai konteks halaman (Inbox untuk messages, Users untuk contacts, dll).

### 3B.4 — Buat Komponen Reusable (opsional)

Jika ada 3+ halaman dengan empty state serupa, buat `frontend/src/components/shared/EmptyState.tsx`:

```tsx
interface EmptyStateProps {
  icon: LucideIcon;
  title: string;       // Indonesian
  titleEn?: string;    // English
  hint?: string;
  action?: { label: string; onClick: () => void };
}
```

---

## Langkah 3C — Subcommand: `loading`

**Tujuan**: User tidak melihat blank page saat data sedang dimuat.

### 3C.1 — Scan Loading State yang Ada

```bash
grep -rn "isLoading\|loading\|useState.*false.*loading" frontend/src/pages/ 2>/dev/null | head -20
```

### 3C.2 — Identifikasi Pages yang Butuh Skeleton

Untuk setiap page yang fetch data via API (ada `useEffect` + `api.get`), cek apakah sudah ada loading state. Jika tidak ada:

### 3C.3 — Tambahkan Skeleton Screens

Untuk list/card pages, buat skeleton yang mereplikasi layout konten:

```tsx
// Tambahkan state
const [isLoading, setIsLoading] = useState(true);

// Di useEffect
setIsLoading(true);
api.get(...).then(r => {
  setItems(r.data);
}).finally(() => setIsLoading(false));

// Di render
if (isLoading) return (
  <div className="space-y-3 p-4">
    {[...Array(5)].map((_, i) => (
      <div key={i} className="h-16 bg-gray-100 rounded-xl animate-pulse" />
    ))}
  </div>
);
```

Untuk page detail, gunakan skeleton yang sesuai struktur konten (header, body, sidebar).

### 3C.4 — Buat Komponen `Skeleton.tsx`

Buat `frontend/src/components/ui/Skeleton.tsx` dengan variants:

```tsx
export function SkeletonLine({ width = "full" }: { width?: string }) {...}
export function SkeletonCard() {...}
export function SkeletonList({ count = 5 }: { count?: number }) {...}
export function SkeletonAvatar() {...}
```

---

## Langkah 3D — Subcommand: `error`

**Tujuan**: Saat terjadi error (network, server, validasi), user mendapat pesan yang jelas dan actionable, bukan blank screen atau console error.

### 3D.1 — Scan Error Handling Saat Ini

```bash
grep -rn "catch\|\.catch\|onError\|isError" frontend/src/pages/ 2>/dev/null | grep -v "//\|console"
grep -rn "toast\|alert\|notification\|snackbar" frontend/src/ 2>/dev/null | head -10
```

### 3D.2 — Buat Error Boundary Component

Buat `frontend/src/components/shared/ErrorBoundary.tsx`:

```tsx
class ErrorBoundary extends React.Component {
  // Catches render errors, tampilkan fallback UI
  // Bilingual error message
  // Tombol "Coba lagi / Try again" yang reload
}
```

### 3D.3 — Buat Toast/Alert System (jika belum ada)

Cek apakah sudah ada toast library (react-hot-toast, sonner, react-toastify):

```bash
grep -E "toast|sonner|toastify" frontend/package.json 2>/dev/null
```

Jika belum ada, install sonner (ringan, modern):
```bash
cd frontend && pnpm add sonner
```

Tambahkan `<Toaster />` ke AppShell/root dan buat helper `toast.error(message)` yang konsisten.

### 3D.4 — Wire Error Handling ke API Calls

Untuk setiap `.catch()` yang hanya `console.log`, tambahkan user-facing feedback:

```tsx
api.get(...).catch((err) => {
  toast.error(
    err.response?.status === 401
      ? "Sesi berakhir. Silakan login kembali."
      : "Gagal memuat data. Coba lagi."
  );
});
```

---

## Langkah 3E — Subcommand: `bilingual`

**Tujuan**: Seluruh UI yang menghadap user menggunakan bahasa Indonesia sebagai primer dan English sebagai sekunder (atau sebaliknya sesuai project).

### 3E.1 — Audit Teks Saat Ini

```bash
# Temukan semua string hardcoded di pages dan components
grep -rn '"[A-Z][a-z].*"' frontend/src/pages/ 2>/dev/null | grep -v "//\|className\|import\|http" | head -30
grep -rn "'[A-Z][a-z].*'" frontend/src/pages/ 2>/dev/null | grep -v "//\|className\|import" | head -30
```

### 3E.2 — Buat Laporan Gap

Kategorikan teks yang ditemukan:
- ✅ Sudah bilingual (ada tanda " / " antara dua bahasa)
- ⚠️ Hanya satu bahasa, perlu ditambah
- ❌ Placeholder (TODO, Lorem ipsum)

### 3E.3 — Tambahkan Teks Bilingual

Untuk setiap teks yang hanya satu bahasa, tambahkan versi kedua dengan pola:

```tsx
// Pola inline (untuk teks pendek):
<p>Tambah Prospect <span className="text-gray-400">/ Add Prospect</span></p>

// Pola subtitle (untuk label dan hint):
<p className="font-medium">Belum ada data</p>
<p className="text-sm text-gray-400">No data yet</p>

// Pola tooltip/hint (untuk action buttons):
title="Tambah / Add"
```

Prioritaskan: buttons, empty states, error messages, modal titles, navigation labels.

---

## Langkah 3F — Subcommand: `audit`

**Tujuan**: Buat laporan komprehensif UX tanpa mengubah kode. Ini adalah entry point yang aman untuk proyek baru.

### 3F.1 — Jalankan Semua Audit

Jalankan semua scan dari langkah 3B.1, 3C.1, 3D.1, 3E.1 secara berurutan.

### 3F.2 — Buat Laporan `UX_AUDIT.md`

```markdown
# UX Audit Report
**Project**: [nama]  
**Date**: [tanggal]  
**Audited by**: Claude Code UX Agent

---

## Summary Score

| Area | Score | Status |
|------|-------|--------|
| Onboarding | 0/5 | ❌ Belum ada |
| Empty States | 2/6 pages | ⚠️ Partial |
| Loading States | 4/6 pages | ⚠️ Partial |
| Error Handling | 1/6 pages | ❌ Perlu perhatian |
| Bilingual | 30% coverage | ⚠️ Partial |

---

## Detail Temuan

### Onboarding
[list halaman tanpa panduan user]

### Empty States
[list halaman yang perlu perbaikan]

### Loading States
[list halaman tanpa loading indicator]

### Error Handling
[list API calls tanpa error feedback]

### Bilingual Coverage
[teks yang hanya satu bahasa]

---

## Prioritas Perbaikan

**High** (berdampak langsung ke user baru):
1. ...

**Medium** (meningkatkan kepercayaan):
1. ...

**Low** (polish):
1. ...

---

## Cara Menjalankan Perbaikan

```bash
# Perbaiki semua sekaligus:
/ux onboard
/ux empty
/ux loading
/ux error
/ux bilingual

# Atau fokus pada satu area:
/ux empty
```
```

---

## Langkah 4 — Type Check & Lint

Setelah setiap subcommand selesai, jalankan:

```bash
# Cek TypeScript
cd frontend && npx tsc --noEmit 2>&1 | tail -20

# Jika ada error, perbaiki sebelum lanjut
```

Jika ada error TypeScript, perbaiki sebelum melanjutkan ke langkah berikutnya.

---

## Langkah 5 — Git Commit

```bash
git add -A
git commit -m "feat(ux): [subcommand] — [ringkasan singkat perubahan]

Co-Authored-By: Claude Code UX Agent <noreply@anthropic.com>"
```

---

## Langkah 6 — Laporan ke User

Tampilkan ringkasan di terminal:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✨ UX ENHANCEMENT — [SUBCOMMAND]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Files diubah  : N files
Components    : [daftar komponen baru/diubah]
Pages updated : [daftar halaman yang diupdate]
TypeScript    : ✅ 0 errors

Perubahan utama:
• [bullet point ringkas per perubahan]

Langkah selanjutnya:
• /ux [subcommand lain yang relevan]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Catatan Reusability

Skill ini bekerja di project apapun selama:
1. Frontend menggunakan React + TypeScript
2. Ada folder `frontend/src/pages/` atau `src/pages/`
3. Styling menggunakan Tailwind CSS
4. Ikon menggunakan `lucide-react` (atau sesuaikan)

Untuk project non-React (Vue, Svelte), sesuaikan pola komponen tapi logika audit tetap berlaku.

Untuk project tanpa backend (static site), skip langkah seed endpoint di `onboard`.
