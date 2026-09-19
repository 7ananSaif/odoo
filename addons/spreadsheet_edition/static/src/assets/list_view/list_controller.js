import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";
import { _t } from "@web/core/l10n/translation";
import { useInsertInSpreadsheet } from "../view_hook";

patch(ListController.prototype, {
    setup() {
        super.setup();
        this.insertInSpreadsheet = useInsertInSpreadsheet(this.env, () =>
            this.getExportableFields()
                .filter((f) => f.type !== "properties")
                .filter(
                    (f) =>
                        Object.values(this.archInfo.fieldNodes).find((fN) => fN.name === f.name)
                            .widget !== "handle"
                )
        );
    },

    getStaticActionMenuItems() {
        const list = this.model.root;
        const isM2MGrouped = list.groupBy.some((groupBy) => {
            const fieldName = groupBy.split(":")[0];
            return list.fields[fieldName].type === "many2many";
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
});
