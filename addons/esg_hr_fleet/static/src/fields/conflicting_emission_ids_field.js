import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { getFormattedValue } from "@web/views/utils";
import { useService } from "@web/core/utils/hooks";

import { Component } from "@odoo/owl";

export class ConflictingEmissionIdsField extends Component {
    static template = "esg_hr_fleet.ConflictingEmissionIdsField";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.actionService = useService("action");
    }

    get conflictingEmissions() {
        return this.props.record.data[this.props.name].records.map((r) => ({
            ...r,
            data: Object.fromEntries(
                Object.keys(r.data).map((fieldName) => [fieldName, getFormattedValue(r, fieldName)])
            ),
        }));
    }

    async showConflictingEmissions() {
        if (this.props.record.isNew) {
            await this.props.record.save({ noReload: true });
        }
        this.actionService.doActionButton({
            type: "object",
            resId: this.props.record.resId,
            name: "action_see_conflicting_emissions",
            resModel: "employee.commuting.emissions.wizard",
        });
    }
}

export const conflictingEmissionIdsField = {
    component: ConflictingEmissionIdsField,
    supportedTypes: ["many2many"],
    relatedFields: () => [
        { name: "date", type: "date" },
        { name: "date_end", type: "date" },
    ],
};

registry.category("fields").add("conflicting_emission_ids", conflictingEmissionIdsField);
