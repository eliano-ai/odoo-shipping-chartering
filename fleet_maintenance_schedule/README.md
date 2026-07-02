# fleet_maintenance_schedule

Custom Odoo 19 module — Fleet Maintenance Schedule

## Overview

Modul ini menambahkan fitur penjadwalan maintenance kendaraan armada yang terintegrasi penuh dengan modul **Fleet**, **Maintenance**, **Inventory (Stock)**, dan **Mail/Calendar** Odoo.

---

## Fitur Utama

### 1. Tab Maintenance Schedule di Form Kendaraan
- Tab baru **"Maintenance Schedule"** muncul di form `fleet.vehicle`
- Tampilkan daftar jadwal maintenance langsung dari kendaraan
- Smart button counter dengan highlight bila ada jadwal yang due
- Warning alert jika ada jadwal jatuh tempo dalam 7 hari

### 2. Model `fleet.maintenance.schedule`
- Auto-sequence: `FMS/YYYY/MM/XXXX`
- 4 tipe maintenance: Preventive, Corrective, Predictive, Overhaul
- Trigger ganda: Date (time-based) + Odometer/Engine Hours
- Reminder email (hari sebelum)

### 3. Workflow State Machine
```
Draft → Confirmed → In Progress → Done
           ↓
        Cancelled (dari state apapun kecuali Done)
```
| Transisi        | Actor                          | Side Effect                              |
|-----------------|--------------------------------|------------------------------------------|
| → Confirmed     | Fleet Manager                  | Auto-create `maintenance.request`        |
|                 |                                | Schedule mail activity reminder          |
| → In Progress   | Fleet Manager, Technician      | Update status maintenance request        |
| → Done          | Fleet Manager, Technician      | Buat `stock.picking` konsumsi spare parts|

### 4. Integrasi Modul

#### Maintenance (maintenance.request)
- Saat schedule di-Confirm, sistem otomatis membuat `maintenance.request`
- Status request ikut berubah saat schedule progress
- Smart button di form schedule untuk akses langsung ke request

#### Calendar / Activity (mail.activity)
- Saat Confirm, activity reminder dibuat di user yang ditugaskan
- Tanggal reminder = `scheduled_date - reminder_days`

#### Inventory (stock.picking)
- Saat Done, sistem membuat Internal Transfer untuk konsumsi spare parts
- Smart button di form schedule untuk akses ke picking

#### Email Otomatis (ir.cron)
- Cron job harian (07:00) mengirim email reminder
- Target: `technician_id.email` atau `fleet_manager_id.email`
- Field `reminder_sent` mencegah pengiriman duplikat

---

## Instalasi

```bash
# Salin modul ke addons path
cp -r fleet_maintenance_schedule /path/to/odoo/custom_addons/

# Install via Odoo
# Settings > Technical > Activate Developer Mode
# Apps > Update App List
# Search "Fleet Maintenance Schedule" > Install
```

## Dependensi

```
fleet, maintenance, stock, mail
```

## Security Groups

| Grup | Akses |
|------|-------|
| **Fleet Manager** | Full CRUD semua record |
| **Maintenance Technician** | Read + Write (hanya record yang di-assign ke mereka) |

---

## Struktur File

```
fleet_maintenance_schedule/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── fleet_maintenance_schedule.py   # Model utama + part line
│   └── fleet_vehicle.py                # Extend fleet.vehicle
├── views/
│   ├── fleet_maintenance_schedule_views.xml  # Form, List, Calendar, Pivot, Template Email
│   ├── fleet_vehicle_views.xml               # Extend form vehicle + tab baru
│   └── fleet_maintenance_schedule_menu.xml   # Menu Fleet > Maintenance
├── security/
│   ├── fleet_maintenance_security.xml   # Groups + Record Rules
│   └── ir.model.access.csv
└── data/
    ├── ir_sequence_data.xml   # Auto-sequence FMS/YYYY/MM/XXXX
    └── ir_cron_data.xml       # Daily reminder cron
```

---

## Versi

`19.0.1.0.0` — Initial release
