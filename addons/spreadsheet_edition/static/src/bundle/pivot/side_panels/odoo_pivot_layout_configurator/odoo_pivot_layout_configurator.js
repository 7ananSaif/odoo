import { components } from "@odoo/o-spreadsheet";
import { ODOO_AGGREGATORS } from "@spreadsheet/pivot/pivot_helpers";
import { ModelFieldSelector } from "@web/core/model_field_selector/model_field_selector";
import { ModelFieldSelectorPopover } from "@web/core/model_field_selector/model_field_selector_popover";
import { _t } from "@web/core/l10n/translation";
import { usePopover } from "@web/core/popover/popover_hook";
const { PivotLayoutConfigurator } = components;

/**
 * This override prevents following relations for many2many fields.
 */
export class PivotModelFieldSelectorPopover extends ModelFieldSelectorPopover {
    static template = "spreadsheet_edition.PivotModelFieldSelectorPopover";

    canFollowRelationFor(fieldDef) {
        if (fieldDef.type === "many2many" || !fieldDef.store) {
            return false;
        }
        return super.canFollowRelationFor(fieldDef);
    }

    duplicateTooltip(alreadyPresent) {
        return alreadyPresent ? _t("Pivot contains duplicate groupbys") : undefined;
    }

    filter(fieldDefs, path) {
        const RELATIONAL_FIELDS = new Set(["many2one", "one2many"]);
        const DATE_FIELDS = new Set(["date", "datetime"]);
        const result = {};
        for (const key in fieldDefs) {
            const field = fieldDefs[key];
            if (!field.groupable) {
                continue;
            }
            const isFieldAlreadyPresent = this.props.filter(field, path);
            if (RELATIONAL_FIELDS.has(field.type)) {
                result[key] = { ...field, isFieldAlreadyPresent };
            } else if (!isFieldAlreadyPresent || DATE_FIELDS.has(field.type)) {
                result[key] = field;
            }
        }
        return result;
    }
}

export class PivotModelFieldSelector extends ModelFieldSelector {
    static template = "spreadsheet_edition.PivotModelFieldSelector";
    static components = {
        Popover: PivotModelFieldSelectorPopover,
    };

    setup() {
        super.setup();
        // Patch popover to add o_spreadsheet_pivot_field_selector class to override dark mode style
        this.popover = usePopover(this.constructor.components.Popover, {
            popoverClass: "o_popover_field_selector o_spreadsheet_pivot_field_selector",
            onClose: async () => {
                if (this.newPath !== null) {
                    const fieldInfo = await this.fieldService.loadFieldInfo(
                        this.props.resModel,
                        this.newPath
                    );
                    this.props.update(this.newPath, fieldInfo);
                }
            },
        });
    }
}

export class OdooPivotLayoutConfigurator extends PivotLayoutConfigurator {
    static template = "spreadsheet_edition.OdooPivotLayoutConfigurator";
    static components = {
        ...PivotLayoutConfigurator.components,
        PivotModelFieldSelector,
    };

    setup() {
        super.setup(...arguments);
        this.AGGREGATORS = ODOO_AGGREGATORS;
    }

    get allDimensions() {
        return this.props.definition.rows.concat(this.props.definition.columns);
    }

    isFieldAlreadyPresent(field, path) {
        const fullField = path ? `${path}.${field.name}` : field.name;
        return this.allDimensions.some((f) => f.fieldName === fullField);
    }
}
