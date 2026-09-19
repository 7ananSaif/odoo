import { registry } from "@web/core/registry";
import { SelectionField, selectionField } from "@web/views/fields/selection/selection_field";

export class CarrierTypeSelection extends SelectionField {
    get options() {
        const carrierTypes = this.props.record.context.carrier_types;
        if (carrierTypes) {
            return Object.entries(carrierTypes).map(([carrier, _]) => [carrier, carrier]);
        } else {
            return [];
        }
    }

    onChange(value) {
        this.props.record.update({ [this.props.name]: value }, { save: this.props.autosave });
    }
}

export const carrierTypeSelection = {
    ...selectionField,
    supportedTypes: ["char"],
    component: CarrierTypeSelection,
};

registry.category("fields").add("carrier_type_selection", carrierTypeSelection);
