import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";

const cogMenuRegistry = registry.category("cogMenu");
/**
 * 'Import records' menu
 *
 * This component is used to import the records for particular model.
 * @extends Component
 */
export class DocumentImportCogMenu extends Component {
    static template = "sign.import.documents.DocumentImportCogMenu";
    static components = { DropdownItem };
    static props = {};

    setup() {
        this.action = useService("action");
    }

    openDocumentImportWizard() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sign.import.documents",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            name: _t("Import from Documents"),
        });
    }
}

cogMenuRegistry.add(
    "document-import-cog-menu",
    {
        Component: DocumentImportCogMenu,
        groupNumber: 15,
        isDisplayed: async ({ config, isSmall, searchModel }) => {
            const hasGroupDocumentsUser = await user.hasGroup("documents.group_documents_user");
            const isSignModel = ["sign.request", "sign.template"].includes(searchModel.resModel);
            const isActionWindow = config.actionType === "ir.actions.act_window";
            return (
                !isSmall &&
                isSignModel &&
                hasGroupDocumentsUser &&
                isActionWindow &&
                config.viewType !== "form"
            );
        },
    },
    { sequence: 1 }
);
