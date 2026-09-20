import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import {EmployeeDeclarationListController} from "./hr_payroll_employee_declaration_list_controller";

export const EmployeeDeclarationListView = Object.assign({}, listView, {
    ...listView,
    Controller: EmployeeDeclarationListController,
});

registry.category("views").add("employee_declaration_list", EmployeeDeclarationListView);
