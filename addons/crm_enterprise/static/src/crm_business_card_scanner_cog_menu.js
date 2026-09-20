import { Component } from "@odoo/owl";
import { CrmBusinessCardScanner } from "./crm_business_card_scanner";
import { registry } from "@web/core/registry";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { isMobileOS } from "@web/core/browser/feature_detection";


const cogMenuRegistry = registry.category("cogMenu");

export class CrmBusinessCardsScannerCogMenu extends Component {
    static template = "crm_enterprise.CrmBusinessCardsScannerCogMenu";
    static components = { DropdownItem, CrmBusinessCardScanner };
    static props = {};

    setup() {
        super.setup();
        this.isMobileOS = isMobileOS();
    }

    onItemSelected() {
        const businessCardScanner = document.querySelector('.o_crm_business_card_scanner input[type="file"]');
        if (businessCardScanner) {
            businessCardScanner.dispatchEvent(new MouseEvent('click'));
        }
    }
}

cogMenuRegistry.add(
    "crm-business-cards-scanner-menu",
    {
        Component: CrmBusinessCardsScannerCogMenu,
        groupNumber: 1,
        isDisplayed: (env) =>
            env.searchModel.resModel === "crm.lead" &&
            ["kanban", "list"].includes(env.config.viewType),
    },
    { sequence: 11 }
);
