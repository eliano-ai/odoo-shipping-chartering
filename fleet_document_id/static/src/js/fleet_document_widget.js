/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted } from "@odoo/owl";

/**
 * FleetDocDaysWidget — colours the days_remaining field
 * green / amber / red depending on value.
 * Registered as a field widget so it can be used in views:
 *   <field name="days_remaining" widget="fleet_doc_days"/>
 */
class FleetDocDaysWidget extends Component {
    static template = "fleet_document_id.DaysRemainingBadge";
    static props = {
        value: { type: Number },
        ...Component.props,
    };

    get badgeClass() {
        const v = this.props.value;
        if (v < 0)   return "badge text-bg-danger";
        if (v <= 7)  return "badge text-bg-danger";
        if (v <= 30) return "badge text-bg-warning";
        return "badge text-bg-success";
    }

    get label() {
        const v = this.props.value;
        if (v < 0) return `${Math.abs(v)} hari lewat`;
        if (v === 0) return "Hari ini";
        return `${v} hari`;
    }
}

// Simple inline template via the template registry
registry.category("templates").add("fleet_document_id.DaysRemainingBadge", `
    <span t-attf-class="{{ badgeClass }}" style="font-size:11px;">
        <t t-esc="label"/>
    </span>
`);

registry.category("fields").add("fleet_doc_days", {
    component: FleetDocDaysWidget,
    displayName: "Fleet Doc Days Remaining",
    supportedTypes: ["integer"],
});
