import { ListController } from "@web/views/list/list_controller";
import { CrmBusinessCardScanner } from "./crm_business_card_scanner";
import { isMobileOS } from "@web/core/browser/feature_detection";

export class CrmBusinessCardScannerListController extends ListController {
    static template = "crm_enterprise.CrmBusinessCardScannerListController";

    static components = {
        ...ListController.components,
        CrmBusinessCardScanner,
    };

    setup() {
        super.setup();
        this.isMobileOS = isMobileOS();
    }
}
