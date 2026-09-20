import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import {
    BadgeSelectionField,
    badgeSelectionField,
} from "@web/views/fields/badge_selection/badge_selection_field";

export class BadgeSelectionIconMappingField extends BadgeSelectionField {
    static template = "appointment.BadgeSelectionIconMappingField";
    static props = {
        ...BadgeSelectionField.props,
        iconMapping: { type: Object, optional: true },
    };

    getIconMapping(selectionValue) {
        return this.props.iconMapping?.[selectionValue] || 'fa-check';
    }
}

export const badgeSelectionIconMappingField = {
    ...badgeSelectionField,
    component: BadgeSelectionIconMappingField,
    displayName: _t("Badges with Icon for Selection Field"),
    supportedTypes: ["selection"],
    extractProps({ options }) {
        return {
            ...badgeSelectionField.extractProps(...arguments),
            iconMapping: options.icon_mapping,
        };
    },
};

registry.category("fields").add("selection_badge_icon_mapping", badgeSelectionIconMappingField);
