import { registry } from "@web/core/registry";
import { AccrualListController } from "./accrual_list_controller";
import { AccrualListSearchModel } from "./accrual_list_search_model";
import { listView } from "@web/views/list/list_view";


export const accrualListView = {
    ...listView,
    buttonTemplate: "account_reports.AccrualListView.Buttons",
    Controller: AccrualListController,
    SearchModel: AccrualListSearchModel,
};

registry.category("views").add("accrual_list_view", accrualListView);
