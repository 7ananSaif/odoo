
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { STATIC_ACTIONS_GROUP_NUMBER } from "@web/search/action_menus/action_menus";

const cogMenuRegistry = registry.category("cogMenu");

export class MultipleAppraisalsCogMenu extends Component {
    static template = "hr_appraisal.MultipleAppraisalsCogMenu";
    static components = { DropdownItem };
    static props = {};

    setup() {
        this.action = useService("action");
    }

    async openAppraisalCampaignWizard() {
        return this.action.doAction("hr_appraisal.action_open_appraisal_campaign_wizard");
    }
}

export const multipleAppraisalsCogMenu = {
    Component: MultipleAppraisalsCogMenu,
    groupNumber: STATIC_ACTIONS_GROUP_NUMBER,
    isDisplayed: async ({ config, searchModel }) => {
        return (
            ["hr.appraisal"].includes(searchModel.resModel) &&
            ["kanban", "list"].includes(config.viewType) &&
            (await user.hasGroup("hr_appraisal.group_hr_appraisal_user"))
        );
    },
};

cogMenuRegistry.add("multiple-appraisals-cog-menu", multipleAppraisalsCogMenu, { sequence: 11 });
