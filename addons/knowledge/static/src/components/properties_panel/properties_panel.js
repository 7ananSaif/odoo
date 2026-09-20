import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { PropertiesField } from "@web/views/fields/properties/properties_field";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";

import { Component, onWillStart, useEffect, useState } from "@odoo/owl";

export class KnowledgeArticleProperties extends Component {
    static template = "knowledge.KnowledgeArticleProperties";
    static props = { ...standardWidgetProps };
    static components = { PropertiesField };

    setup() {
        this.state = useState(this.env.propertiesPanelState);
        this.ui = useService("ui");
        // open/close the panel based on the existence of properties
        useEffect(
            () => {
                if (!this.ui.isSmall && this.hasProperties && !this.state.isDisplayed) {
                    this.state.isDisplayed = true;
                } else if (this.state.isDisplayed && !this.hasProperties) {
                    this.state.isDisplayed = false;
                }
            },
            () => [this.props.record.resId, this.hasProperties]
        );
        onWillStart(async () => (this.userIsInternal = await user.hasGroup("base.group_user")));
    }

    get hasProperties() {
        return this.props.record.data.article_properties.some((prop) => !prop.definition_deleted);
    }
}

export const knowledgePropertiesPanel = {
    component: KnowledgeArticleProperties,
    additionalClasses: [
        "col-12",
        "col-lg-2",
        "p-0",
        "position-relative",
        "border-top",
    ],
    fieldDependencies: [{ name: "article_properties", type: "jsonb" }],
};

registry.category("view_widgets").add("knowledge_properties_panel", knowledgePropertiesPanel);
