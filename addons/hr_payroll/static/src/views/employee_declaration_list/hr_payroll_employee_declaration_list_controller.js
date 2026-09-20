import {ListController} from "@web/views/list/list_controller";
import {useService} from "@web/core/utils/hooks";

export class EmployeeDeclarationListController extends ListController {
    static template = "hr_payroll.EmployeeDeclarationListController";

    setup() {
        super.setup();
        this.orm = useService("orm")
        this.action = useService("action");
    }

    getNumberToGenerate() {
        return this.onlyDrafts() ? "" : this.model.root.selection.filter((r) => r.data.state === "draft").length
    }

    noDrafts(){
        if (this.hasSelectedRecords)
            return this.model.root.selection.filter((r) => r.data.state === "draft").length < 1
        return this.model.root.records.filter((r) => r.data.state === "draft").length < 1
    }

    onlyDrafts(){
        if (this.hasSelectedRecords)
            if (this.model.root.selection.filter((r) => r.data.state === "draft").length === this.model.root.selection.length)
                return true
        return this.model.root.records.filter((r) => r.data.state === "draft").length === this.model.root.records.length;
    }

    checkOnlyDrafts() {
        return this.onlyDrafts() ? "btn-primary" : "btn-secondary"
    }

    generatePdfs(){
        return this.action.doActionButton({
            type: "object",
            resModel: "hr.payroll.employee.declaration",
            name:"action_generate_pdf",
            resIds: this.model.root.selection.filter((r) => r.data.state === "draft").map((r) => r.resId),
        })
    }
}
