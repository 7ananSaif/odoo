import {Component} from "@odoo/owl";

import {registry} from "@web/core/registry";
import {DropdownItem} from "@web/core/dropdown/dropdown_item";
import {useService} from "@web/core/utils/hooks";

const cogMenuRegistry = registry.category("cogMenu");

export class GeneratePdfsCogMenu extends Component {
    static template = "hr_payroll.GeneratePdfsCogMenu";
    static components = {DropdownItem};
    static props = {};

    setup() {
        this.action = useService("action");
    }

    generatePdfs() {
        this.unhighlightDraftRecords();
        return this.action.doActionButton({
            type: "object",
            resModel: "hr.payroll.employee.declaration",
            name:"action_generate_pdf",
            resIds: this.env.model.root.records.filter((r) => r.data.state === "draft").map((r) => r.resId),
        });
    }

    highlightDraftRecords() {
        if (this.env.model.root.selection.length) return;
        let table_row = document.getElementsByClassName("o_data_row");
        this.env.model.root.records.forEach((draft_declaration, index) => {
            if (index + 1 > table_row.length) return;
            if (draft_declaration.data.state === "draft") table_row[index].classList.add("table-info");
        });
    }

    unhighlightDraftRecords() {
        Array.from(document.getElementsByClassName("o_data_row"))
            .forEach(row => {
                if (!row.classList.contains("o_data_row_selected"))
                    row.classList.remove("table-info");
            });
    }

    draftRecords() {
        return this.env.model.root.records.filter((r) => r.data.state === "draft").length;
    }
}

export const GeneratePdfsCogMenuItem = {
    Component: GeneratePdfsCogMenu,
    isDisplayed: async ({config, searchModel}) => {
        return (
            searchModel.resModel === "hr.payroll.employee.declaration" &&
            config.viewType === "list" &&
            config.actionType === "ir.actions.act_window"
        );
    },
    groupNumber: 1,
};

cogMenuRegistry.add("generate-pdf-menu", GeneratePdfsCogMenuItem, {sequence: 10});
