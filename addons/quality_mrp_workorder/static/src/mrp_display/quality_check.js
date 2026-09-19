import { patch } from "@web/core/utils/patch";
import { QualityCheck } from "@mrp_workorder/mrp_display/mrp_record_line/quality_check";
import { useState } from "@odoo/owl";
import { MrpMeasureDialog } from "./mrp_measure_dialog";

patch(QualityCheck.prototype, {
    setup() {
        super.setup();
        this.state = useState({ reOpened: false });
    },
    get icon() {
        switch (this.type) {
            case "passfail":
                return this.isComplete ? "fa fa-undo" : "fa fa-check";
            case "measure":
                return "fa fa-arrows-h";
            case "spreadsheet":
                return "fa fa-th";
            default:
                return super.icon;
        }
    },
    get barcode() {
        switch (this.type) {
            case "passfail":
                return "PASS";
            default:
                return super.barcode;
        }
    },
    get showQty() {
        if (this.type === "measure" && this.isComplete) {
            const { measure, norm_unit } = this.props.record.data;
            return this.passed ? (measure + ' ' + norm_unit) : "failed";
        } else if (this.passFailTypes.includes(this.type) && this.isComplete) {
            return this.passed ? "passed" : "failed";
        }
        return super.showQty;
    },
    get activeClass() {
        return this.type === "passfail" ? "btn-success" : super.activeClass;
    },
    get isActive() {
        return this.state.reOpened || super.isActive;
    },
    get passFailTypes() {
        return ["passfail", "measure", "spreadsheet"];
    },
    async clicked() {
        switch (this.type) {
            case "passfail":
                if (this.isComplete) {
                    this.state.reOpened = true;
                    this.props.record.data.quality_state = "none";
                    return;
                } else {
                    this.state.reOpened = false;
                    return this.doActionAndNext("action_pass_and_next");
                }
            case "measure":
                return this.dialog.add(MrpMeasureDialog, {
                    record: this.props.record,
                    confirm: this.saveMeasurement.bind(this),
                });
            case "spreadsheet":
                await this.props.startWorking();
                const { model, resModel, resId } = this.props.record;
                const result = await model.orm.call(resModel, "action_open_spreadsheet", [resId]);
                result.params = {
                    ...result.params,
                    pass_action: "action_pass_and_next",
                    fail_action: "action_fail_and_next"
                };
                return this.action.doAction(result);
            default:
                return super.clicked();
        }
    },
    async saveMeasurement() {
        await this.props.record.save({ reload: false });
        return this.doActionAndNext("do_measure");
    },
    failCheck() {
        this.state.reOpened = false;
        return this.doActionAndNext("action_fail_and_next", "fail");
    },
});
