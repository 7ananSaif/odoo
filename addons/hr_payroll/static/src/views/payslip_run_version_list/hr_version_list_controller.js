import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";

export class VersionPayrunListController extends ListController {

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.state = useState({
            disabled: false,
        });
    }

    async onReload() {
        return this.actionService.doAction({type: "ir.actions.client", tag: "soft_reload"});
    }

    async onClose() {
        return this.actionService.doAction({type: "ir.actions.act_window_close"});
    }

    buildRawRecord(rawRecord) {
        return {
            ...rawRecord,
            date_start: luxon.DateTime.fromISO(rawRecord.date_start).toISODate(),
            date_end: luxon.DateTime.fromISO(rawRecord.date_end).toISODate(),
            structure_id: rawRecord.structure_id.id,
            company_id: rawRecord.company_id?.id,
        };
    }

    async generatePayslips() {
        this.state.disabled = true;
        const selectedVersions = await this.model.root.getResIds(true);
        if (selectedVersions.length < 1) return;
        let ids = [this.props.context.active_id];
        if (this.props.context.raw_record) {
            const rawRecord = this.buildRawRecord(this.props.context.raw_record);
            ids = await this.orm.create("hr.payslip.run", [rawRecord]);
        }
        try {
            await this.orm.call(
                "hr.payslip.run",
                "generate_payslips",
                [ids],
                {
                    version_ids: selectedVersions,
                });
            if (this.props.context.raw_record) {
                await this.openPayslips(ids);
            }
            await this.onClose();
            await this.onReload();
        } finally {
            this.state.disabled = false;
        }
    }

    async openPayslips(ids){
        const action = await this.orm.call("hr.payslip.run", "action_open_payslips", [ids]);
        return this.actionService.doAction(action);
    }

    async onBack(){
        const rawRecord = this.buildRawRecord(this.props.context.raw_record);
        return this.actionService.doAction("hr_payroll.action_hr_payslip_run_create", {
            additionalContext: Object.fromEntries(
                Object.entries(rawRecord).map(([key, value]) => [`default_${key}`, value])
            ),
        });
    }
}
export const versionPayrunListController = {
    ...listView,
    Controller: VersionPayrunListController,
    buttonTemplate: "hr_payroll.VersionPayrunListController.Buttons",
};

registry.category("views").add("hr_version_payrun_list", versionPayrunListController);
