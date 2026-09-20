import { Component, useEffect, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ActionMenus } from "@web/search/action_menus/action_menus";
import { SIZES } from "@web/core/ui/ui_service";

export class DocumentsAction extends Component {
    static template = "documents.DocumentsAction";
    static components = {
        ActionMenus,
    };
    static props = {
        targetRecords: Array,
        folderId: [String, Number, Boolean],
        isPreview: { type: Boolean, optional: true },
    };

    setup() {
        this.documentService = useService("document.document");
        this.state = useState({
            topbarActions: [],
            actionMenuProps: null,
        });
        this.ui = useState(useService("ui"));
        useEffect(() => {
            if (this.documentService.getSelectionActions) {
                const selectionActions = this.documentService.getSelectionActions();
                this.state.topbarActions = Object.values(this.documentService.getSelectionActions().getTopbarActions()).sort((a, b) => b.groupNumber - a.groupNumber)
                if (this.props.isPreview) {
                    const actionMenuProps = selectionActions.getMenuProps();
                    actionMenuProps.items.action = actionMenuProps.items.action.filter(
                        this.isPreviewAction
                    );
                    this.state.actionMenuProps = actionMenuProps;
                }
            }
        }, () => [this.props.targetRecords, this.ui.isSmall]);
    }

    get topbarActions() {
        return this.state.topbarActions.filter(
            (action) => !action.isAvailable || action.isAvailable()
        );
    }

    get visibleTopbarActions() {
        return this.ui.size >= SIZES.XL ? 3 : 2;
    }

    isPreviewAction(action) {
        return action.key !== "export";
    }
}
