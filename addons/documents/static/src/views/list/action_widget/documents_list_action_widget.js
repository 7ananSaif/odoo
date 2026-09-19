import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

import { DocumentsListActionItemDetails } from "./documents_list_action_item_details";
import { DocumentsListActionItemDownload } from "./documents_list_action_item_download";
import { DocumentsListActionItemOpenFolder } from "./documents_list_action_item_open_folder";
import { DocumentsListActionItemRename } from "./documents_list_action_item_rename";
import { DocumentsListActionItemShare } from "./documents_list_action_item_share";

export class DocumentsListActionWidget extends Component {
    static props = { ...standardWidgetProps };
    static template = "documents.DocumentsListActionWidget";

    static actionItems = [
        DocumentsListActionItemShare,
        DocumentsListActionItemDownload,
        DocumentsListActionItemRename,
        DocumentsListActionItemDetails,
        DocumentsListActionItemOpenFolder,
    ];
}

export const documentsListActionWidget = {
    component: DocumentsListActionWidget,
};

registry.category("view_widgets").add("documents_list_actions", documentsListActionWidget);
