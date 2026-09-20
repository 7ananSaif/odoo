import { mapView } from "@web_map/map_view/map_view";
import { registry } from "@web/core/registry";

import { Component, useState } from "@odoo/owl";
import { InteractiveEditorSidebar } from "@web_studio/client_action/view_editor/interactive_editor/interactive_editor_sidebar";
import { Property } from "@web_studio/client_action/view_editor/property/property";
import { SidebarViewToolbox } from "@web_studio/client_action/view_editor/interactive_editor/sidebar_view_toolbox/sidebar_view_toolbox";
import { Many2ManyTagsField } from "@web/views/fields/many2many_tags/many2many_tags_field";
import { useEditNodeAttributes } from "@web_studio/client_action/view_editor/view_editor_model";
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";
import { fieldsToChoices } from "@web_studio/client_action/view_editor/editors/utils";

export class MapEditorSidebar extends Component {
    static template = "web_studio.ViewEditor.MapEditorSidebar";
    static props = {
        openViewInForm: { type: Function, optional: true },
        openDefaultValues: { type: Function, optional: true },
    };
    static components = {
        InteractiveEditorSidebar,
        Property,
        SidebarViewToolbox,
        Many2ManyTagsField,
        MultiRecordSelector,
    };

    setup() {
        this.viewEditorModel = useState(this.env.viewEditorModel);
        this.editArchAttributes = useEditNodeAttributes({ isRoot: true });
    }

    get modelParams() {
        return this.viewEditorModel.controllerProps.modelParams;
    }

    get multiRecordSelectorProps() {
        return {
            resModel: "ir.model.fields",
            update: this.changeAdditionalFields.bind(this),
            resIds: this.currentAdditionalFieldsIds,
            domain: [
                ["model", "=", this.viewEditorModel.resModel],
                ["ttype", "not in", ["many2many", "one2many", "binary"]],
            ],
        };
    }

    get currentAdditionalFieldsIds() {
        return (
            JSON.parse(
                this.viewEditorModel.xmlDoc.firstElementChild.getAttribute("studio_map_field_ids")
            ) || []
        );
    }

    onViewAttributeChanged(value, name) {
        value = value ? value : "";
        return this.editArchAttributes({ [name]: value });
    }

    get contactFieldChoices() {
        return Object.values(this.viewEditorModel.fields)
            .filter((field) => field.type === "many2one" && field.relation === "res.partner")
            .map((field) => ({ label: `${field.string} (${field.name})`, value: field.name }));
    }

    get defaultOrderChoices() {
        return Object.values(this.viewEditorModel.fields)
            .filter(
                (field) => field.store && !["one2many", "many2many", "binary"].includes(field.type)
            )
            .map((field) => ({ label: `${field.string} (${field.name})`, value: field.name }));
    }

    get defaultGroupbyChoices() {
        return fieldsToChoices(
            this.viewEditorModel.fields,
            this.viewEditorModel.GROUPABLE_TYPES,
            (field) => field.store
        );
    }

    /**
     * @param {Array<Number>} resIds
     */
    changeAdditionalFields(resIds) {
        const currentFullIds = this.currentAdditionalFieldsIds;
        const newIds = resIds.filter((id) => !currentFullIds.includes(id));
        let toRemoveIds;

        const operationType = newIds.length ? "add" : "remove";

        if (operationType === "remove") {
            toRemoveIds = currentFullIds.filter((id) => !resIds.includes(id));
        }

        this.viewEditorModel.doOperation({
            type: "map_popup_fields",
            target: {
                operation_type: operationType,
                field_ids: operationType === "add" ? newIds : toRemoveIds,
            },
        });
    }

    editDefaultGroupBy(value) {
        this.editArchAttributes({ default_group_by: value.join(",") });
    }
}

registry.category("studio_editors").add("map", {
    ...mapView,
    Sidebar: MapEditorSidebar,
});
