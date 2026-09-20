import { patch } from "@web/core/utils/patch";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { _t } from "@web/core/l10n/translation";
import { useInsertInSpreadsheet } from "../view_hook";

export const patchKanbanControllerExportSelection = {
    setup() {
        super.setup();
        this.insertInSpreadsheet = useInsertInSpreadsheet(this.env, () =>
            this.getExportableFields()
        );
    },

    getStaticActionMenuItems() {
        const root = this.model.root;
        const isM2MGrouped = root.groupBy.some((groupBy) => {
            const fieldName = groupBy.split(":")[0];
            return root.fields[fieldName].type === "many2many";
        });
        const menuItems = super.getStaticActionMenuItems(...arguments);
        menuItems["insert"] = {
            isAvailable: () => !isM2MGrouped,
            sequence: 15,
            icon: "oi oi-view-list",
            description: _t("Insert in spreadsheet"),
            callback: () => this.insertInSpreadsheet(),
        };
        return menuItems;
    },
};

export const unpatchKanbanControllerExportSelection = patch(
    KanbanController.prototype,
    patchKanbanControllerExportSelection
);
