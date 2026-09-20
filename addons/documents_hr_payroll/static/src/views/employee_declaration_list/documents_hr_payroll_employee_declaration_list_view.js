import {registry} from "@web/core/registry";

import {EmployeeDeclarationListView} from "../../../../../hr_payroll/static/src/views/employee_declaration_list/hr_payroll_employee_declaration_list_view";
import {DocumentsEmployeeDeclarationListController} from "./documents_hr_payroll_employee_declaration_list_controller";

export const DocumentsEmployeeDeclarationListView = Object.assign({}, EmployeeDeclarationListView, {
    ...EmployeeDeclarationListView,
    Controller: DocumentsEmployeeDeclarationListController,
});

registry.category("views").add("employee_declaration_list", DocumentsEmployeeDeclarationListView, {force: true});
