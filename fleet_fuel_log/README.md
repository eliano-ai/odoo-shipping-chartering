# fleet_fuel_log

Custom Odoo 19 module — Fleet Fuel Log & Consumption Tracking

## Overview

Modul pencatatan BBM armada dengan dukungan penuh untuk operasional **maritim (MFO/HSD)** dan kendaraan darat, terintegrasi dengan **Inventory (stock)** dan **Accounting (journal entry)**.

---

## Fitur Utama

### 1. Master Jenis BBM (`fleet.fuel.type`)
- Solar/HSD, Marine Fuel Oil (MFO), Marine Gas Oil (MGO), dll.
- Konfigurasi per jenis: produk Inventory, akun beban, threshold anomali, harga default

### 2. Fuel Log (`fleet.fuel.log`)
Tiga tipe transaksi:
| Tipe | Keterangan |
|------|-----------|
| `refuel` | Pengisian di SPBU / Bunker |
| `daily` | Pemakaian harian berbasis odometer |
| `trip` | Konsumsi per Trip / Voyage |

Field utama: tanggal, kendaraan, jenis BBM, odometer start/end, volume (L), harga/L, total cost, konsumsi L/100km, jam mesin (untuk MFO/kapal).

### 3. Workflow Approval
```
Draft → To Approve → Approved → Posted
                ↓
           Cancelled
```
| Transisi | Actor | Side Effect |
|----------|-------|-------------|
| → To Approve | Driver / Fleet Manager | Cek anomali, kirim email jika terdeteksi |
| → Approved | Fleet Manager only | Buat `stock.move` konsumsi BBM |
| → Posted | Fleet Manager only | Buat `account.move` (journal entry biaya BBM) |

### 4. Anomaly Detection
- Auto-compute `consumption_rate` (L/100km)
- Bandingkan dengan rata-rata 20 log terakhir kendaraan tersebut
- Jika melebihi `threshold%` → `is_anomaly = True`
- Email otomatis ke Fleet Manager (template + cron harian jam 06:00)
- Banner merah di form view saat anomali terdeteksi

### 5. Trip / Voyage (`fleet.vehicle.trip`)
- Kumpulkan multiple fuel log dalam satu trip/voyage
- Hitung total fuel cost, avg consumption, distance per trip
- Workflow: Planned → Ongoing → Done
- Smart button di form Trip untuk akses fuel logs

### 6. Integrasi Inventory
- Saat **Approved**: buat `stock.move` internal (konsumsi dari warehouse ke production)
- Konfigurasi produk BBM per `fleet.fuel.type`

### 7. Integrasi Accounting
- Saat **Posted**: buat `account.move` (journal entry)
  - Debit: akun beban BBM (konfigurasi per fuel type)
  - Credit: akun utang/payable perusahaan
- Smart button di form untuk akses langsung ke journal entry

### 8. Tab & Smart Buttons di Vehicle
- Tab **Fuel Logs** di form kendaraan: KPI (cost YTD, avg consumption) + inline list
- Smart buttons: jumlah fuel log, jumlah trips

### 9. Laporan
- **Pivot**: analisis cost per kendaraan × jenis BBM × bulan
- **Graph**: trend konsumsi & biaya (line chart)
- Menu: `Fleet > Fuel > Fuel Report`

---

## Instalasi

```bash
cp -r fleet_fuel_log /path/to/odoo/custom_addons/
# Settings > Apps > Update App List > Install "Fleet Fuel Log"
```

## Dependensi
```
fleet, stock, account, mail
```

## Security Groups

| Grup | Hak Akses |
|------|-----------|
| **Fleet Manager** | Full CRUD, approve, post, cancel semua record |
| **Driver / Operator** | Buat Draft + baca record sendiri saja |

---

## Struktur File

```
fleet_fuel_log/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── fleet_fuel_type.py          # Master jenis BBM
│   ├── fleet_fuel_log.py           # Model utama (504+ baris)
│   ├── fleet_vehicle_trip.py       # Trip / Voyage
│   └── fleet_vehicle.py            # Extend fleet.vehicle
├── views/
│   ├── fleet_fuel_type_views.xml
│   ├── fleet_fuel_log_views.xml    # Form, List, Pivot, Graph, Email template
│   ├── fleet_vehicle_trip_views.xml
│   ├── fleet_vehicle_views.xml     # Tab Fuel di form kendaraan
│   └── fleet_fuel_log_menu.xml     # Menu Fleet > Fuel
├── report/
│   └── fleet_fuel_report_views.xml # Fuel Cost Report action
├── security/
│   ├── fleet_fuel_security.xml     # Groups + record rules
│   └── ir.model.access.csv
└── data/
    ├── ir_sequence_data.xml        # FFL/YYYY/MM/XXXX
    ├── fleet_fuel_type_data.xml    # Master: HSD, MFO, MGO
    └── ir_cron_data.xml            # Daily anomaly check cron
```

---

## Konfigurasi Awal (Post-Install)

1. **Fleet > Fuel > Fuel Types** — set `product_id`, `account_id`, `anomaly_threshold_pct` per jenis BBM
2. Pastikan produk BBM di Inventory sudah dikonfigurasi (tipe: `Consumable` atau `Storable`)
3. Pastikan akun beban BBM ada di Chart of Accounts
4. Assign user ke group **Fleet Manager** atau **Driver / Operator**

---

## Versi

`19.0.1.0.0` — Initial release
