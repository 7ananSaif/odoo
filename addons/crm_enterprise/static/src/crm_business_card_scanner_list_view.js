import { CrmBusinessCardScannerListController } from "./crm_business_card_scanner_list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";


export const CrmBusinessCardsScannerListView = {
    ...listView,
    Controller: CrmBusinessCardScannerListController,
};

registry.category("views").add("crm_business_cards_scanner_list", CrmBusinessCardsScannerListView);
