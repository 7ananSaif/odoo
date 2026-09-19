import { registry } from "@web/core/registry";
import { SelectionField, selectionField } from "@web/views/fields/selection/selection_field";

const WRITE_VALUE_PREFIX = "write_";

export class DocumentsMixedSelectionField extends SelectionField {
    static template = "documents.DocumentsMixedSelectionField";
    static props = {
        ...SelectionField.props,
        excludeNone: { type: Boolean, optional: true },
    };
    static defaultProps = {
        excludeNone: false,
    };

    setup() {
        super.setup();
        this.originalValue = this.props.record.data[this.props.name];
    }

    /**
     * @override
     */
    get options() {
        return super.options.filter(
            ([code, __]) =>
                // Keep the original value
                code === this.originalValue ||
                // Keep only the ${WRITE_VALUE_PREFIX}_xx options except the one for original value
                (code.startsWith(WRITE_VALUE_PREFIX) &&
                    code !== `${WRITE_VALUE_PREFIX}${this.originalValue}` &&
                    // Remove ${WRITE_VALUE_PREFIX}_none if excludeNone is set
                    (code !== `${WRITE_VALUE_PREFIX}none` || !this.props.excludeNone))
        );
    }
}

export const documentsMixedSelectionField = {
    ...selectionField,
    component: DocumentsMixedSelectionField,
    extractProps({ options }) {
        const props = selectionField.extractProps(...arguments);
        props.excludeNone = Boolean(options.exclude_none);
        return props;
    },
};

registry.category("fields").add("documents_mixed_selection", documentsMixedSelectionField);
