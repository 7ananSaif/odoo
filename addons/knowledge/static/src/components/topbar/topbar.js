import KnowledgeHierarchy from "@knowledge/components/hierarchy/hierarchy";
import { OptionsDropdown } from "@knowledge/components/options_dropdown/options_dropdown";
import { PermissionPanel } from "@knowledge/components/permission_panel/permission_panel";
import { PermissionPanelDialog } from "../permission_panel_dialog/permission_panel_dialog";
import { _t } from "@web/core/l10n/translation";
import { usePopover } from "@web/core/popover/popover_hook";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { useRecordObserver } from "@web/model/relational_model/utils";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

import { Component, onWillStart, reactive, useState } from "@odoo/owl";

class KnowledgeTopbar extends Component {
    static template = "knowledge.KnowledgeTopbar";
    static props = standardWidgetProps;
    static components = {
        KnowledgeHierarchy,
        OptionsDropdown,
    };

    setup() {
        super.setup();

        this.dialog = useService("dialog");
        this.permissionPopover = usePopover(PermissionPanel, {
            closeOnClickAway: true,
            arrow: false,
            onClose: () => (this.state.shareBtnIsActive = false),
            position: "bottom-end",
        });
        this.state = useState({
            shareBtnIsActive: false,
        });
        this.commentsState = useState(this.env.commentsState);
        this.chatterPanelState = useState(this.env.chatterPanelState);
        this.propertiesPanelState = useState(this.env.propertiesPanelState);

        onWillStart(async () => {
            this.isInternalUser = await user.hasGroup("base.group_user");
        });

        this.reactiveRecordWrapper = reactive({ record: this.props.record });
        useRecordObserver((record) => {
            this.reactiveRecordWrapper.record = record;
        });
    }

    get chatterButtonTitle() {
        return this.chatterPanelState.isDisplayed
            ? _t("Close chatter panel")
            : _t("Open chatter panel");
    }

    get commentButtonTitle() {
        return this.commentsState.isDisplayed
            ? _t("Close comments panel")
            : _t("Open comments panel");
    }

    get favoriteButtonTitle() {
        return this.props.record.data.is_user_favorite
            ? _t("Remove from favorites")
            : _t("Add to favorites");
    }

    togglePermissionPanel(event) {
        if (this.env.isSmall && !this.state.shareBtnIsActive) {
            this.dialog.add(PermissionPanelDialog, {
                reactiveRecordWrapper: this.reactiveRecordWrapper,
                openArticle: this.env.openArticle,
                sendArticleToTrash: this.env.sendArticleToTrash
            });
        } else if (this.permissionPopover.isOpen) {
            this.permissionPopover.close();
        } else {
            if (this.props.record.dirty) {
                this.props.record.save();
            }
            this.permissionPopover.open(event.currentTarget, {
                reactiveRecordWrapper: this.reactiveRecordWrapper,
                openArticle: this.env.openArticle,
                sendArticleToTrash: this.env.sendArticleToTrash
            });
            this.state.shareBtnIsActive = true;
        }
    }
}

export const knowledgeTopbar = {
    component: KnowledgeTopbar,
    fieldDependencies: [
        { name: "create_uid", type: "many2one", relation: "res.users" },
        { name: "display_name", type: "char" },
        { name: "last_edition_uid", type: "many2one", relation: "res.users" },
        { name: "active", type: "boolean" },
        { name: "article_properties", type: "jsonb" },
        { name: "cover_image_id", type: "many2one", relation: "knowledge.cover" },
        { name: "full_width", type: "boolean" },
        { name: "icon", type: "char" },
        { name: "inherited_permission", type: "char"},
        { name: "inherited_permission_parent_id", type: "many2one", relation: "knowledge.article"},
        { name: "is_article_item", type: "boolean" },
        { name: "is_locked", type: "boolean" },
        { name: "is_desynchronized", type: "boolean"},
        { name: "is_user_favorite", type: "boolean" },
        { name: "name", type: "char" },
        { name: "parent_id", type: "char" },
        { name: "parent_path", type: "char" },
        { name: "root_article_id", type: "many2one", relation: "knowledge.article" },
        { name: "has_item_parent", type: "boolean" },
        { name: "is_listed_in_templates_gallery", type: "boolean" },
        { name: "to_delete", type: "boolean" },
        { name: "user_can_write", type: "boolean" },
    ],
};

registry.category("view_widgets").add("knowledge_topbar", knowledgeTopbar);
