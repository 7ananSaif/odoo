/* eslint-disable no-console */
/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, useState } from "@odoo/owl";

/**
 * Invoice Suggestion Panel — inline Accept/Reject chips for AI extraction.
 *
 * Used on the bill form as `widget="invoice_suggestion_panel"` bound to
 * `extraction_line_ids` (a one2many, so the widget gets the record's
 * `resId`, `model` and `data`). Each chip runs `orm.call` against
 * `account.move.apply_suggested_value` with exactly one field name, so a
 * single click applies exactly one value — the backend re-reads the value
 * from the persisted `extraction_json` payload, never from the client.
 *
 * The spent ("accepted" / "rejected") chips are kept locally so the panel
 * does not flicker while the form reloads; `record.load()` refreshes the
 * real data after each apply.
 */
export class InvoiceSuggestionPanel extends Component {
    static template = "invoice_agent.suggestion_panel";

    // The form renderer passes `id`, `name`, `readonly` and `record` — not the
    // `fieldInfo` descriptor — so the bound field name is `props.name`.
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        // Plain objects (not Sets): Owl's reactivity observes property writes,
        // not Set mutations, so a Set would mutate without re-rendering the
        // panel — no spinner, no disabled state, and chips never disappearing.
        this.state = useState({
            applying: {}, // field_name -> true while a call is in flight
            spent: {}, // field_name -> true once accepted or rejected
        });
    }

    // ------------------------------------------------------------------
    // State
    // ------------------------------------------------------------------
    get suggestions() {
        const fieldName = this.props.name;
        if (!fieldName) {
            return [];
        }
        const data = this.props.record?.data?.[fieldName] || {};
        return (data.records || []).filter(
            (suggestion) => !this.state.spent[suggestion.data?.field_name]
        );
    }

    get busy() {
        return Object.values(this.state.applying).some(Boolean);
    }

    get disabled() {
        return this.props.readonly || this.busy;
    }

    // ------------------------------------------------------------------
    // Actions
    // ------------------------------------------------------------------
    async acceptSuggestion(suggestion) {
        const fieldName = suggestion.data?.field_name;
        if (!fieldName || this.state.applying[fieldName]) {
            return; // double-click guard: one call per field
        }
        this.state.applying[fieldName] = true;
        try {
            await this.orm.call(
                this.props.record.model,
                "apply_suggested_value",
                [this.props.record.resId],
                { field_name: fieldName }
            );
            this.state.spent[fieldName] = true;
        } catch (error) {
            // Keep the chip visible so the accountant can retry after fixing
            // the underlying issue (e.g. vendor not found).
            console.warn("invoice_agent: apply_suggested_value failed", error);
            throw error;
        } finally {
            this.state.applying[fieldName] = false;
        }
        await this.props.record.load();
    }

    async rejectSuggestion(suggestion) {
        const fieldName = suggestion.data?.field_name;
        if (!fieldName || this.state.applying[fieldName]) {
            return;
        }
        this.state.spent[fieldName] = true;
        // Rejection is purely local: no backend write. A later "Suggest with
        // AI" run regenerates the full suggestion set.
    }
}

// Register the widget so `widget="invoice_suggestion_panel"` resolves. The
// panel binds to the `extraction_line_ids` one2many, whose records expose
// `data.field_name`, `data.extracted_value` and `data.field_confidence`.
export const invoiceSuggestionPanel = {
    component: InvoiceSuggestionPanel,
    supportedTypes: ["one2many"],
    relatedFields: [
        { name: "field_name", type: "char" },
        { name: "extracted_value", type: "text" },
        { name: "field_confidence", type: "float" },
    ],
    extractProps({ attrs }) {
        return {
            readonly: attrs.readonly ? attrs.readonly === "True" : false,
        };
    },
};

registry.category("fields").add("invoice_suggestion_panel", invoiceSuggestionPanel);
