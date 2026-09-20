import { crmKanbanView } from "@crm/views/crm_kanban/crm_kanban_view";
import { CrmBusinessCardScanner } from "./crm_business_card_scanner";
import { isMobileOS } from "@web/core/browser/feature_detection";

export class CrmBusinessCardScannerKanbanController extends crmKanbanView.Controller {
    static template = "crm_enterprise.CrmBusinessCardScannerKanbanController";

    static components = {
        ...crmKanbanView.Controller.components,
        CrmBusinessCardScanner,
    };

    setup() {
        super.setup();
        this.isMobileOS = isMobileOS();
    }
}
