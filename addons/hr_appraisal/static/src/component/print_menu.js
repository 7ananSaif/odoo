import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

const cogMenuRegistry = registry.category("cogMenu");

export class PrintActionMenu extends Component {
    static template = "hr_appraisal.PrintAction";
    static components = { DropdownItem };
    static props = {};

    async print() {
        window.print()
    }
}

export const printActionMenu = {
    Component: PrintActionMenu,
    isDisplayed: async ({ config, searchModel }) => {
        return (
            ["hr.appraisal"].includes(searchModel.resModel) &&
            ["form"].includes(config.viewType)
        );
    },
};

cogMenuRegistry.add("print-action-menu", printActionMenu, { sequence: 11 });
