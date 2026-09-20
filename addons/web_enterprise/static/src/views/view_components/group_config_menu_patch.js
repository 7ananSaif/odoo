import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { GroupConfigMenu } from "@web/views/view_components/group_config_menu";
import { PromoteStudioAutomationDialog } from "@web_enterprise/webclient/promote_studio/promote_studio_dialog";

patch(GroupConfigMenu.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
    },
    /**
     * @override
     */
    get permissions() {
        const permissions = super.permissions;
        Object.defineProperty(permissions, "canEditAutomations", {
            get: () => user.isAdmin,
            configurable: true,
        });
        return permissions;
    },

    async openAutomations() {
        if (typeof this._openAutomations === "function") {
            // this is the case if base_automation is installed
            return this._openAutomations();
        } else {
            this.env.services.dialog.add(PromoteStudioAutomationDialog, {
                title: _t("Odoo Studio - Customize workflows in minutes"),
            });
        }
    },
});

registry.category("group_config_items").add(
    "open_automations",
    {
        label: _t("Automations"),
        method: "openAutomations",
        isVisible: ({ permissions }) => permissions.canEditAutomations,
        class: "o_column_automations",
        icon: "fa-magic",
    },
    { sequence: 25, force: true }
);
