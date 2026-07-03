/** @odoo-module **/

import { Component, onMounted, onWillStart, onWillUnmount, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const MARKER_COLORS = {
    available: "#6c757d",
    on_voyage_charter: "#0F6E56",
    on_time_charter: "#1F4E79",
    chartered_in: "#854F0B",
};

const STATUS_LABELS = {
    available: "Tersedia",
    on_voyage_charter: "Voyage Charter Aktif",
    on_time_charter: "Time Charter Aktif",
    chartered_in: "Charter-In Aktif",
};

export class FleetMapDashboard extends Component {
    static template = "vessel_voyage_operations.FleetMapDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.mapContainerRef = useRef("mapContainer");
        this.map = null;
        this.vessels = [];

        onWillStart(async () => {
            this.vessels = await this.orm.searchRead(
                "fleet.vehicle",
                [["is_vessel", "=", true]],
                ["name", "current_position_lat", "current_position_lng", "charter_status"]
            );
        });

        onMounted(() => this.renderMap());
        onWillUnmount(() => {
            if (this.map) {
                this.map.remove();
                this.map = null;
            }
        });
    }

    renderMap() {
        const L = window.L;
        const withPosition = this.vessels.filter(
            (v) => v.current_position_lat && v.current_position_lng
        );

        this.map = L.map(this.mapContainerRef.el, { scrollWheelZoom: true });

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: "&copy; OpenStreetMap contributors",
            maxZoom: 18,
        }).addTo(this.map);

        if (withPosition.length) {
            const bounds = L.latLngBounds(
                withPosition.map((v) => [v.current_position_lat, v.current_position_lng])
            );
            this.map.fitBounds(bounds, { padding: [40, 40], maxZoom: 8 });
        } else {
            // Fallback: pusatkan di perairan Indonesia kalau belum ada posisi kapal sama sekali.
            this.map.setView([-2.5, 118], 5);
        }

        for (const vessel of withPosition) {
            const color = MARKER_COLORS[vessel.charter_status] || MARKER_COLORS.available;
            const label = STATUS_LABELS[vessel.charter_status] || vessel.charter_status;
            const icon = L.divIcon({
                className: "o_vessel_marker",
                html: `<div class="o_vessel_marker_dot" style="background-color:${color};"></div>`,
                iconSize: [18, 18],
                iconAnchor: [9, 9],
            });
            L.marker([vessel.current_position_lat, vessel.current_position_lng], { icon })
                .addTo(this.map)
                .bindPopup(
                    `<b>${vessel.name}</b><br/>${label}<br/>` +
                    `<span class="text-muted">${vessel.current_position_lat.toFixed(4)}, ` +
                    `${vessel.current_position_lng.toFixed(4)}</span>`
                );
        }
    }
}

registry.category("actions").add("vessel_voyage_operations.fleet_map_dashboard", FleetMapDashboard);
