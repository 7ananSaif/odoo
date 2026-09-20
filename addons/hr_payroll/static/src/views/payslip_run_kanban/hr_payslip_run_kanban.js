import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { registry } from "@web/core/registry";
import { KanbanRecord } from "@web/views/kanban/kanban_record";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { KanbanHeader } from "@web/views/kanban/kanban_header";
import { useOpenPayRun } from "../payslip_run_hook";
import { PayRunKanbanCompiler } from "./hr_payslip_run_kanban_compiler";
import { PayRunButtonBox } from "../../components/payrun_card/button_box/payrun_button_box";

class PayrunKanbanController extends KanbanController {
    static components = {
        ...KanbanController.components,
    };

    /**
     * @override
     */
    setup() {
        super.setup();
        this.openPayRun = useOpenPayRun();
    }

    async openRecord(record, { newWindow } = {}) {
        this.openPayRun({ id: record.resId });
    }

    async createRecord() {
        this.openPayRun({});
    }
}

export class PayrunKanbanHeader extends KanbanHeader {
    static template = "hr_payroll.PayrunKanbanHeader";
}

export class PayrunKanbanRecord extends KanbanRecord {
    static menuTemplate = "hr_payroll.PayrunKanbanRecordMenu";
    static components = {
        ...KanbanRecord.components,
        PayRunButtonBox,
    };
}

export class PayrunKanbanRenderer extends KanbanRenderer {
    static template = "hr_payroll.PayrunKanbanRenderer";

    static components = {
        ...KanbanRenderer.components,
        KanbanHeader: PayrunKanbanHeader,
        KanbanRecord: PayrunKanbanRecord,
    };
}

const PayrunKanbanView = {
    ...kanbanView,
    Controller: PayrunKanbanController,
    Compiler: PayRunKanbanCompiler,
    Renderer: PayrunKanbanRenderer,
};

registry.category("views").add("payslip_run_kanban", PayrunKanbanView);
