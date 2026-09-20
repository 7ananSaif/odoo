import { Component } from "@odoo/owl";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";

const cogMenuRegistry = registry.category("cogMenu");


export class RefreshAccountReturns extends Component {
    static template = "account_reports.RefreshAccountReturns";
    static components = { DropdownItem };
    static props = {};

    async refresh_all_account_returns() {
        await this.env.services.orm.call("account.return", "action_refresh_all_returns");
        await this.env.model.load();
    }
}

export const refreshAccountReturns = {
    Component: RefreshAccountReturns,
    groupNumber: 5,
    isDisplayed: ({ config }) => {
        return config.actionType === "ir.actions.act_window" &&
        ["kanban"].includes(config.viewType) &&
        ["account_return_kanban"].includes(config.viewSubType);
    },
};

cogMenuRegistry.add("refresh-account-returns-menu", refreshAccountReturns, { sequence: 10 });
