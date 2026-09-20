import {EmployeeDeclarationListController} from "../../../../../hr_payroll/static/src/views/employee_declaration_list/hr_payroll_employee_declaration_list_controller";

export class DocumentsEmployeeDeclarationListController extends EmployeeDeclarationListController{
    static template = "hr_payroll.DocumentsEmployeeDeclarationListController"

    setup() {
        super.setup();
    }

    getNumberToPost() {
        return this.onlyGenerated() ? "" : this.model.root.selection.filter((r) => r.data.state === "pdf_generated").length
    }

    noGenerated(){
        if (this.hasSelectedRecords)
            return this.model.root.selection.filter((r) => r.data.state === "pdf_generated").length < 1
        return this.model.root.records.filter((r) => r.data.state === "pdf_generated").length < 1
    }

    onlyGenerated(){
        if (this.hasSelectedRecords)
            if (this.model.root.selection.filter((r) => r.data.state === "pdf_generated").length === this.model.root.selection.length)
                return true
        return this.model.root.records.filter((r) => r.data.state === "pdf_generated").length === this.model.root.records.length;
    }

    checkOnlyGenerated() {
        return this.onlyGenerated() ? "btn-primary" : "btn-secondary"
    }

    postPdfs(){
        return this.action.doActionButton({
            type: "object",
            resModel: "hr.payroll.employee.declaration",
            name: "action_post_in_documents",
            resIds: this.model.root.selection.filter((r) => r.data.state === "pdf_generated").map((r) => r.resId),
        })
    }
}
