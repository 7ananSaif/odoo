import { PermissionPanel } from "@knowledge/components/permission_panel/permission_panel";
import { Dialog } from "@web/core/dialog/dialog";
import { Component } from "@odoo/owl";

/**
 * This component is used exclusively on mobile devices to render the permissions
 * panel within a fullscreen dialog. The fullscreen mode improves usability by
 * providing a more accessible interface for managing article permissions and members.
 */
export class PermissionPanelDialog extends Component {
    static template = "knowledge.PermissionPanelDialog";
    static components = { Dialog, PermissionPanel };
    static props = {
        reactiveRecordWrapper: Object,
        openArticle: Function,
        sendArticleToTrash: Function,
        close: Function
    };
}
