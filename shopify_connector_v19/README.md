# Shopify Connector untuk Odoo 19

**Developed by:** PT Sun Artha Putra Mandiri (Sunartha)
**Odoo Version:** 19
**Shopify API Version:** 2026-01
**Module Version:** 19.0.1.0.0
**Module Technical Name:** `shopify_connector_v19`

---

## Daftar Isi

1. [Overview](#overview)
2. [Features](#features)
3. [Requirements](#requirements)
4. [Setup Shopify Partner Account & Development Store](#1-setup-shopify-partner-account--development-store)
5. [Buat Custom App di Shopify (Dev Dashboard)](#2-buat-custom-app-di-shopify-dev-dashboard)
6. [Install Dependency — Queue Job (OCA)](#3-install-dependency--queue-job-oca)
7. [Install Module Shopify Connector di Odoo](#4-install-module-shopify-connector-di-odoo)
8. [Assign Access Rights (Security Group)](#5-assign-access-rights-security-group)
9. [Konfigurasi Store di Odoo](#6-konfigurasi-store-di-odoo)
10. [Location Mapping](#7-location-mapping)
11. [Test Connection & Register Webhooks](#8-test-connection--register-webhooks)
12. [Initial Bulk Sync](#9-initial-bulk-sync)
13. [Verifikasi di Storefront](#10-verifikasi-di-storefront)
14. [Required Shopify API Scopes](#required-shopify-api-scopes)
15. [Troubleshooting](#troubleshooting)
16. [Known Limitations](#known-limitations)

---

## Overview

Bidirectional integration antara Shopify dan Odoo 19. Connector ini sync products, inventory, orders, customers, dan tracking numbers. Support multi-company dan multi-store setup.

Arsitektur: **Odoo = source of truth** untuk products/inventory/prices. **Shopify = source of truth** untuk orders/payments. Mapping key utama menggunakan **SKU**.

## Features

- Product & variant sync (Odoo → Shopify)
- Inventory sync per warehouse/location (Odoo → Shopify)
- Fixed pricing per Shopify Market (Odoo → Shopify)
- Order import dengan multi-company routing (Shopify → Odoo)
- Customer sync (Shopify → Odoo)
- Tracking number sync setelah fulfillment (Odoo → Shopify)
- Refund & cancellation handling
- Webhook-based real-time sync + polling fallback (15 menit)
- Dashboard monitoring, logging, dan alerts

## Requirements

- Odoo 19 Enterprise
- Python 3.12+
- Module: `queue_job` dari OCA branch `19.0`
- Python library: `requests` (sudah bundled dengan Odoo)
- Shopify Partner account (gratis)
- Folder custom addons (misal `odoocustom/`) yang sudah terdaftar di `addons_path`

---

## 1. Setup Shopify Partner Account & Development Store

Sebelum install apapun di Odoo, siapkan dulu Shopify-nya.

### 1.1 Buat Shopify Partner Account

1. Buka [partners.shopify.com](https://partners.shopify.com)
2. Klik **Join as a Partner**
3. Isi data registrasi (nama, email, nama perusahaan — bisa pakai nama Sunartha)
4. Verifikasi email
5. Login ke Partner Dashboard

### 1.2 Buat Development Store

1. Di Partner Dashboard, klik **Stores** di sidebar kiri
2. Klik **Add store**
3. Pilih tipe **Dev** — *"Testing, dev, or staging environments"*
4. Isi:
   - **Store name** — bebas, misal `sunarthatest`
   - **Shopify plan** — pilih **Basic** (gratis untuk dev store, plan tidak mempengaruhi fitur API)
5. Centang ✅ **Generate test data for store** — ini akan preload store dengan produk sample dan bogus payment gateway, sangat membantu untuk testing tanpa harus input data manual
6. **Jangan** centang "Test a feature preview on this store" — tidak diperlukan
7. Klik **Create store**

Setelah ini kamu akan punya store dengan URL `<nama-store>.myshopify.com`.

---

## 2. Buat Custom App di Shopify (Dev Dashboard)

> **Catatan penting:** Sejak 1 Januari 2026, Shopify men-deprecate "legacy custom app" untuk merchant biasa. Tapi sebagai **Partner**, kamu masih bisa membuat app via **Dev Dashboard**, yang merupakan cara modern dan direkomendasikan Shopify saat ini.

### 2.1 Masuk ke App Development

1. Di Shopify Admin store kamu → **Settings → Apps and sales channels**
2. Klik **Develop apps**
3. Klik **Build apps in Dev Dashboard**

### 2.2 Buat App Baru

1. Klik **Create app**
2. Isi:
   - **App name:** `Sunartha Odoo Connector`
   - **App developer:** pilih developer yang sesuai (staff/collaborator dengan permission develop apps)
3. Klik **Create app**

### 2.3 Configure Admin API Scopes

1. Di halaman App Development Overview, klik **Configure Admin API scopes**
2. Centang semua scope berikut (lihat [list lengkap di bawah](#required-shopify-api-scopes))
3. Save

### 2.4 Configuration — URLs & Webhooks API Version

Masuk ke tab **Configuration**, isi:

| Field | Value |
|---|---|
| App URL | URL Odoo instance kamu, contoh `https://yourodoo.odoo.com` (bisa diisi placeholder dulu kalau Odoo belum live) |
| Embed app in Shopify admin | ❌ Uncheck — tidak diperlukan |
| Preferences URL | Kosongkan |
| **Webhooks API version** | **`2026-01`** ⚠️ — **WAJIB disamakan dengan API version yang dipakai connector** (lihat Store Configuration di Odoo) |
| Use legacy install flow | ❌ Uncheck |
| Redirect URLs | Kosongkan |
| Embed app in Shopify POS | ❌ Uncheck |
| App proxy | Kosongkan semua |

Klik **Release** untuk membuat versi aktif.

### 2.5 Install App & Ambil Credentials

1. Klik **Install app** (tombol di kanan atas halaman app)
2. Konfirmasi install
3. Setelah install, masuk ke tab **API credentials**
4. Di bagian **Admin API access token**, klik **Reveal token once**
5. **Copy dan simpan SEKARANG** — token (`shpat_...`) hanya ditampilkan satu kali
6. Scroll ke bawah, catat juga:
   - **API key** (Client ID)
   - **API secret key** (`shpss_...`) — ⚠️ **ini yang dipakai sebagai Webhook Secret** di Odoo (lihat teks *"Use your client secret to verify incoming webhooks"*)

Simpan ketiga credentials ini di tempat aman (bukan di chat/notes biasa):

| Item | Contoh Format |
|---|---|
| Shop URL | `sunarthatest.myshopify.com` |
| Access Token | `shpat_xxxxxxxxxxxxxxxx` |
| Webhook Secret (API secret key) | `shpss_xxxxxxxxxxxxxxxx` |

---

## 3. Install Dependency — Queue Job (OCA)

Connector ini **depends** pada module `queue_job` untuk async processing (webhook handling tidak boleh blocking, harus respond ke Shopify < 5 detik).

### 3.1 Download

Download dari GitHub:
```
https://github.com/OCA/queue/tree/19.0
```
atau via git clone:
```bash
git clone -b 19.0 https://github.com/OCA/queue.git
```

> ⚠️ **PENTING:** Repo OCA ini berisi BANYAK module (`queue_job`, `queue_job_cron`, `queue_job_batch`, `base_import_async`, dll). **Yang dibutuhkan connector ini HANYA folder `queue_job/`** — module lain bersifat opsional/tidak perlu untuk integrasi ini.

### 3.2 Extract & Pindahkan

1. Extract hasil download
2. Ambil **hanya folder `queue_job/`** dari dalamnya
3. Pastikan nama foldernya tetap **`queue_job`** (jangan di-rename, misal jangan jadi `queue_job_19`) — Odoo membaca nama folder sebagai technical name module, dan dependency di `__manifest__.py` connector ini mereferensikan `queue_job` secara eksak
4. Copy folder `queue_job/` ke addons directory custom kamu (misal `odoocustom/`)

### 3.3 Install

1. Restart Odoo service
2. Aktifkan **Developer Mode** (`Settings → General Settings → Activate Developer Mode`)
3. `Settings → Apps → Update Apps List`
4. Search **"Queue Job"** atau **"Job Queue"**
5. Klik **Activate/Install**
6. Verifikasi berhasil: cek menu `Settings → Technical → Queue Jobs` sudah muncul

---

## 4. Install Module Shopify Connector di Odoo

1. Extract package ini (`shopify_connector_v19.zip`)
2. Pastikan struktur foldernya **`shopify_connector_v19/`** (nama folder = technical name module, jangan diubah)
3. Copy folder tersebut ke addons directory custom (misal `odoocustom/`), sejajar dengan folder `queue_job/`
4. Pastikan path `odoocustom` sudah terdaftar di `odoo.conf`:
   ```
   addons_path = /odoo/addons,/odoo/odoocustom
   ```
5. Restart Odoo
6. `Settings → Apps → Update Apps List`
7. Search **"Shopify Connector"**
8. Klik **Install**

---

## 5. Assign Access Rights (Security Group)

Module ini punya 2 security group: **Shopify / Manager** (full access) dan **Shopify / User** (read-only + trigger sync).

1. `Settings → Users & Companies → Users`
2. Klik user yang akan pakai connector (misal Administrator)
3. Cari section **Shopify** di tab Access Rights
4. Assign ke **Shopify / Manager**
5. Save

> Tanpa step ini, menu "Shopify" tidak akan muncul di navigation bar, dan akses ke wizard (misal Bulk Sync) akan menghasilkan **Access Error**.

---

## 6. Konfigurasi Store di Odoo

1. Masuk ke menu **Shopify → Store Configuration → New**
2. Isi:

| Field | Value |
|---|---|
| Configuration Name | Nama bebas, misal `Sunartha Test Store` |
| Shop URL | `sunarthatest.myshopify.com` (tanpa `https://`) |
| Shopify API Version | `2026-01` (harus sama dengan Webhooks API version di Shopify app config) |
| Access Token | dari step 2.5 |
| Webhook Secret | API secret key dari step 2.5 |
| Company | pilih company Odoo yang sesuai |
| Default Warehouse | pilih warehouse |
| Default Pricelist | opsional |

3. Di tab **Sync Settings**, atur sesuai kebutuhan (Sync Products/Inventory/Orders, Missing SKU Mode, dll)
4. **Save** (klik ikon cloud ☁️)

---

## 7. Location Mapping

Inventory sync butuh tahu warehouse Odoo mana yang map ke location Shopify mana.

### 7.1 Ambil Shopify Location ID

1. Shopify Admin → **Settings → Locations**
2. Klik salah satu location (misal "Shop location")
3. Lihat URL browser, ambil angka di akhir URL:
   ```
   .../settings/locations/89971392559
   ```
4. Format yang dipakai connector adalah **GraphQL Global ID (GID)**, bukan angka biasa:
   ```
   gid://shopify/Location/89971392559
   ```

### 7.2 Isi di Odoo

1. Di Store Configuration, tab **Location Mapping** → **Add a line**
2. Isi:
   - **Odoo Warehouse:** pilih warehouse (misal `Main Warehouse`)
   - **Shopify Location ID:** `gid://shopify/Location/89971392559`
   - **Shopify Location Name:** `Shop location`
   - **Is Primary:** ✅
3. Save

---

## 8. Test Connection & Register Webhooks

1. Klik tombol **Test Connection** — kalau berhasil, muncul notifikasi hijau *"Connection Successful. Connected to: ..."*
2. Klik tombol **Register Webhooks** — kalau berhasil, muncul notifikasi *"Webhooks Registered. All webhooks have been registered to Shopify."*

> Register webhook butuh `web.base.url` di Odoo berupa **HTTPS public URL** (bukan `localhost`). Cek di `Settings → Technical → System Parameters → web.base.url`.

---

## 9. Initial Bulk Sync

Sebelum sync, pastikan minimal ada 1 produk di Odoo dengan **Internal Reference (SKU)** terisi dan **Can be Sold** dicentang.

1. Klik tombol **Bulk Sync**
2. Centang **Sync Products** dan **Sync Inventory**
3. Klik **Run Sync**
4. Tunggu notifikasi *"Bulk Sync Completed. ✓ Products synced. ✓ Inventory synced."*

Cek hasilnya di `Shopify → Sync Logs → All Logs` — pastikan status `success`.

---

## 10. Verifikasi di Storefront

1. Buka `https://<nama-store>.myshopify.com`
2. Kalau muncul halaman password, klik **"Are you the store owner? Log in here"** untuk bypass (karena login sebagai staff/owner)
3. Pastikan produk yang baru di-sync sudah muncul di Storefront

> **Catatan:** produk yang baru dibuat via API biasanya **belum otomatis assign ke Sales Channel "Online Store"** (cek kolom **Channels** di halaman Products — kalau nilainya `0`, produk tidak akan muncul di storefront manapun). Assign manual via halaman produk di Shopify Admin → bagian *Sales channels and apps*.

---

## Required Shopify API Scopes

```
read_products, write_products
read_inventory, write_inventory
read_orders, write_orders
read_customers, write_customers
read_fulfillments, write_fulfillments
write_assigned_fulfillment_orders
read_assigned_fulfillment_orders
```

---

## Troubleshooting

| Error | Kemungkinan Penyebab | Solusi |
|---|---|---|
| Menu "Shopify" tidak muncul | User belum di-assign ke security group | Assign ke Shopify/Manager (lihat step 5) |
| `Access Error: shopify.bulk.sync.wizard` | Access rights wizard tidak terdaftar | Pastikan pakai package versi terbaru yang sudah fix |
| Module tidak terdeteksi / technical name salah | Nama folder tidak sesuai | Pastikan nama folder persis `shopify_connector_v19` |
| `queue_job` dependency error saat install | Queue Job belum terinstall | Install Queue Job dulu (step 3), pastikan nama folder `queue_job` |
| Test Connection: `401 Unauthorized` | Access Token salah/expired | Regenerate token di Shopify App → API credentials |
| Webhook registration gagal | `web.base.url` masih `localhost`/HTTP | Update ke HTTPS public URL |
| Shopify API error: `Field is not defined on ProductInput` (bodyHtml/options/variants) | Versi lama connector pakai schema GraphQL yang sudah deprecated | Pastikan pakai package versi terbaru (sudah pakai `productOptionsCreate` + `productVariantsBulkCreate`) |
| Order tidak masuk ke Odoo otomatis | Webhook tidak terdaftar / Queue Job tidak jalan | Cek `Settings → Technical → Queue Jobs`, cek webhook list di Shopify |
| Harga produk salah (misal Rp 450.000 jadi $450,000) | Currency mismatch antara Odoo base currency dan Shopify store currency | Lihat [Known Limitations](#known-limitations) di bawah |

---

## Known Limitations

- **Tidak ada auto currency conversion.** Connector mengirim angka harga (`lst_price`) langsung ke Shopify **tanpa konversi currency**. Kalau base currency Odoo (misal IDR) berbeda dengan base currency Shopify store (misal USD), angka akan salah tafsir (Rp 450.000 terbaca sebagai $450,000). Untuk production, harga per market/currency **harus** diatur lewat **Pricelist Mapping** (tab di Store Configuration), bukan mengandalkan harga default.
- **Geolocation/Markets-based pricing belum tervalidasi.** Saat testing, harga yang menyesuaikan otomatis berdasarkan Shopify Markets/geolocation **sepertinya belum berjalan sebagaimana mestinya**. Belum jelas apakah ini karena Pricelist Mapping belum dikonfigurasi dengan benar di environment testing, atau ada gap di logic `_sync_product_prices` yang belum align dengan setup Markets di Shopify. **Perlu investigasi lebih lanjut sebelum dianggap production-ready.**
- **Sales Channel assignment tidak dihandle otomatis.** Produk yang baru dibuat via API tidak otomatis ter-assign ke Sales Channel manapun (termasuk "Online Store") — ini di luar scope connector dan perlu di-assign manual di Shopify Admin, atau ditambahkan sebagai automation terpisah kalau diperlukan.
- **Partial refund pada credit note** masih simplified — kalau jumlah refund tidak match persis dengan invoice asli, credit note dibuat tapi mungkin perlu adjustment manual (lihat komentar di `shopify_refund_sync.py`).

---

*Untuk pertanyaan lebih lanjut: ask@sunartha.co.id*
