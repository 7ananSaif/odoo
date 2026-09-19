import { Component } from "@odoo/owl";
import { components } from "@odoo/o-spreadsheet";

const { Section } = components;

export class GlobalFilterFooter extends Component {
    static template = "spreadsheet_edition.GlobalFilterFooter";
    static components = { Section };
    static props = {
        onClickCancel: Function,
        onClickDelete: { type: Function, optional: true },
        onClickSave: { type: Function, optional: true },
    };
}
