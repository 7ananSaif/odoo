import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

import { useService } from "@web/core/utils/hooks";
import { Chatter } from "@mail/chatter/web_portal/chatter";
import { SIZES } from "@web/core/ui/ui_service";

import { Component, useState } from "@odoo/owl";

export class KnowledgeArticleChatter extends Component {
    static template = "knowledge.KnowledgeArticleChatter";
    static components = { Chatter };
    static props = { ...standardWidgetProps };

    setup() {
        this.state = useState(this.env.chatterPanelState);
        this.ui = useService("ui");
    }

    get isChatterAside() {
        return this.ui.size >= SIZES.LG;
    }
}

export const knowledgeChatterPanel = {
    component: KnowledgeArticleChatter,
    additionalClasses: ["border-top", "col-12", "col-lg-4", "position-relative", "p-0"],
};

registry.category("view_widgets").add("knowledge_chatter_panel", knowledgeChatterPanel);
