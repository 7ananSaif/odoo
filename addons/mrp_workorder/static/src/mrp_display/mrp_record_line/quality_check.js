import { MrpWorkorder } from "./mrp_workorder";
import { useService } from "@web/core/utils/hooks";
import { FileUploader } from "@web/views/fields/file_handler";
import { useRef, useState } from "@odoo/owl";
import { MrpWorksheetDialog } from "../dialog/mrp_worksheet_dialog";

export class QualityCheck extends MrpWorkorder {
    static template = "mrp_workorder.QualityCheck";
    static components = {
        ...MrpWorkorder.components,
        FileUploader,
    };
    static props = {
        ...MrpWorkorder.props,
        registerProduction: { type: Function, optional: true },
        qtyProducing: { type: String, optional: true },
        isCurrent: Boolean,
        startWorking: Function,
    };

    setup() {
        this.action = useService("action");
        this.fileUploaderToggle = useRef("fileUploaderToggle");
        this.unique = useState({ epoch: Date.now() });
        this.dialog = useService("dialog");
    }

    get passed() {
        return this.check.quality_state === "pass";
    }

    get failed() {
        return this.check.quality_state === "fail";
    }

    get type() {
        return this.check.test_type;
    }

    get isComplete() {
        return this.passed || this.failed;
    }

    get showImage() {
        return this.passed && this.type === "picture";
    }

    get check() {
        return this.props.record.data;
    }

    get label() {
        return this.check.title || this.check.name;
    }

    get imageUrl() {
        const { resId } = this.props.record;
        return `/web/image/quality.check/${resId}/picture?unique=${this.unique.epoch}`;
    }

    get icon() {
        switch (this.type) {
            case "picture":
                return this.passed ? "mw" : "fa fa-camera";
            case "instructions":
                return this.passed ? "fa fa-undo" : "fa fa-check";
            case "print_label":
                return "fa fa-print";
            case "register_production":
                return "fa fa-plus";
            default:
                return "";
        }
    }

    get barcode() {
        switch (this.type) {
            case "print_label":
                return "PRPL";
            default:
                return "NEXT";
        }
    }

    get isActive() {
        return this.props.isCurrent;
    }

    get activeClass() {
        return "btn-primary";
    }

    get hasInstruction() {
        const { note, worksheet_document } = this.check;
        return (note && note.length) || worksheet_document;
    }

    get showQty() {
        if (this.type === "register_production") {
            const { lot_ids, product_tracking } = this.check;
            if (product_tracking == "lot") {
                return lot_ids.count ? lot_ids.records[0].data.display_name : false;
            }
            if (product_tracking == "serial") {
                const { product_qty, qty_producing } = this.props.record.data.production_id;
                if (product_qty == 1) {
                    return lot_ids.count ? lot_ids.records[0].data.display_name : false;
                }
                return qty_producing ? this.props.qtyProducing : false;
            }
            return this.passed ? this.props.qtyProducing : false;
        }
        return false;
    }

    async clicked() {
        switch (this.type) {
            case "instructions":
                if (this.isComplete) {
                    this.props.record.data.quality_state = "none";
                    return;
                } else {
                    return this.doActionAndNext("action_next");
                }
            case "print_label":
                return this.doActionAndNext("action_print");
            case "picture":
                return this.fileUploaderToggle.el.click();
            case "register_production":
                if (
                    ["lot", "serial"].includes(this.check.product_tracking) &&
                    !this.check.lot_ids.count
                ) {
                    await this.props.record.load();
                }
                return this.props.registerProduction();
        }
    }

    async onFileUploaded(info) {
        await this.props.record.update({ picture: info.data });
        await this.props.record.save({ reload: false });
        await this.doActionAndNext("action_next");
        this.unique.epoch = Date.now();
    }

    async doActionAndNext(action, stateToSet = "pass") {
        const { model, resModel, resId, data, _parentRecord } = this.props.record;
        const result = await model.orm.call(resModel, action, [resId]);
        if ("next_check_id" in result) {
            data.quality_state = stateToSet;
            _parentRecord.data.current_quality_check_id = { id: result.next_check_id };
        }
        if ("type" in result) {
            const params = {};
            if (result.type === "ir.actions.act_window") {
                params.onClose = () => this.env.reload(this.props.record);
                data.quality_state = "none";
            }
            await this.action.doAction(result, params);
        }
        return this.props.startWorking();
    }

    async showWorksheet() {
        let worksheetData = false;
        if (this.check.worksheet_document) {
            const sheet = await this.props.record.model.orm.read(
                "quality.check",
                [this.check.id],
                ["worksheet_document"]
            );
            worksheetData = {
                resModel: "quality.check",
                resId: this.check.id,
                resField: "worksheet_document",
                value: sheet[0].worksheet_document,
                page: 1,
            };
        }
        this.dialog.add(MrpWorksheetDialog, {
            worksheetText: this.check.note,
            worksheetData,
        });
    }
}
