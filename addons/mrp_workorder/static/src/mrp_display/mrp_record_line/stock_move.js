import { _t } from "@web/core/l10n/translation";
import { useActiveActions, useOpenMany2XRecord } from "@web/views/fields/relational_utils";
import { useService } from "@web/core/utils/hooks";
import { QualityCheck } from "./quality_check";
import { MrpQuantityDialog } from "../dialog/mrp_quantity_dialog";
import { MrpSelectQuantDialog } from "../dialog/mrp_select_quant_dialog"; // TODO remove in master

export class StockMove extends QualityCheck {
    static props = {
        ...QualityCheck.props,
        displayUOM: Boolean,
        check: { optional: true, type: Object },
        label: { optional: true, type: String },
        production: Object,
    };
    static template = "mrp_workorder.StockMove";

    setup() {
        this.dialog = useService("dialog");
        this.props.record.component = this;
        if (this.props.check) {
            this.props.check.component = this;
        }
        const activeActions = useActiveActions({
            fieldType: "one2many",
            getEvalParams: (props) => ({
                readonly: props.record.data.has_tracking === "none",
            }),
        });
        this.openQuantRecord = useOpenMany2XRecord({
            resModel: "stock.quant",
            activeActions: activeActions,
            onRecordSaved: (record) => this.selectQuant([record.resId]),
            fieldString: "Move Line",
            is2Many: true,
        });
    }

    get label() {
        const productName = this.props.record.data.product_id.display_name;
        if (this.props.record.data.production_id) {
            return _t("By-product: %(productName)s", { productName });
        }
        return this.check ? super.label : productName;
    }

    get icon() {
        if (this.isTracked) {
            return this.displayCheck ? "check" : "plus"; // Make sure to display check for prefilled quality check moves
        }
        return this.isComplete ? "undo" : "pencil"; // No move lines for untracked moves, work directly on the move
    }

    get isComplete() {
        return this.check ? super.isComplete : Boolean(this.props.record.data.picked);
    }

    get toConsumeQuantity() {
        const move = this.props.record.data;
        return move.should_consume_qty || move.product_uom_qty;
    }

    get quantityDone() {
        const moveLines = this.props.record.data.move_line_ids.records.filter(
            (ml) => (this.isTracked ? ml.data.lot_id : true) && ml.data.picked
        );
        return moveLines.reduce((total, ml) => total + ml.data.quantity, 0);
    }

    get uom() {
        if (this.props.displayUOM) {
            return this.props.record.data.product_uom.display_name;
        }
        return this.toConsumeQuantity === 1 ? _t("Unit") : _t("Units");
    }

    get check() {
        return this.props.check ? this.props.check.data : false;
    }

    get hasInstruction() {
        return this.check ? super.hasInstruction : false;
    }

    get visibleMoveLines() {
        if (!this.isTracked) {
            return [];
        }
        const { move_line_ids, picking_type_prefill_shop_floor_lots } = this.props.record.data;
        return picking_type_prefill_shop_floor_lots
            ? move_line_ids.records
            : move_line_ids.records.filter((ml) => ml.data.picked);
    }

    get displayCheck() {
        return (
            this.check &&
            !this.isComplete &&
            this.props.record.data.picking_type_prefill_shop_floor_lots &&
            this.props.record.data.move_line_ids.records.length
        );
    }

    get isTracked() {
        return this.props.record.data.has_tracking !== "none";
    }

    get byproduct() {
        return this.props.record.data.byproduct_id;
    }

    //TODO remove in master
    addMoveLine() {
        const product = this.props.record.data.product_id;
        this.dialog.add(MrpSelectQuantDialog, {
            resModel: "stock.quant",
            noCreate: !this.isTracked,
            multiSelect: false,
            domain: [["product_id", "=", product.id], ['location_id.usage', '=', 'internal'], ["on_hand", "=", true], ["quantity", ">", 0.0]],
            title: _t("Add line: %(productName)s", { productName: product.display_name }),
            context: {
                single_product: true,
                list_view_ref: "stock.view_stock_quant_tree_simple",
                hide_lot: !this.isTracked,
                hide_available: true,
            },
            onSelected: (resIds) => this.selectQuant(resIds),
            onCreateEdit: () => this.createQuant(),
            record: this.props.record,
        });
    }

    async markAsDone() {
        const { model, resModel, resId, _parentRecord } = this.props.check;
        const result = await model.orm.call(resModel, "action_next", [resId]);
        if ("next_check_id" in result) {
            this.check.quality_state = "pass";
            this.props.record.data.picked = true;
            _parentRecord.data.current_quality_check_id = [result.next_check_id];
        }
    }

    async undo() {
        const { resModel, resId, _parentRecord } = this.props.record;
        await this.props.record.model.orm.call(resModel, "action_undo", [[resId]]);
        await this.env.reload(_parentRecord);
    }

    editUntrackedMove() {
        this.dialog.add(MrpQuantityDialog, {
            record: this.props.record,
            confirm: this.env.reload.bind(this, this.props.record._parentRecord),
        });
    }

    async clicked() {
        if (this.isTracked) {
            if (this.displayCheck) {
                await this.markAsDone(); // check button: accept prefilled values and confirm QC
            } else {
                if (this.byproduct)
                {
                    this.createQuant(); // plus button: create a new move line. Create a new quant for the byproduct.
                } else {
                    this.addMoveLine(); // plus button: create a new move line. Show a list of quants  to take from.
                }
            }
        } else {
            if (this.isComplete) {
                await this.undo(); // undo button: reset move data for untracked move
            } else {
                this.editUntrackedMove(); // pencil button: edit untracked move quantity
            }
        }
        return this.props.startWorking();
    }

    async selectQuant(quantIds) {
        const { resId, model } = this.props.record;
        await model.orm.call("stock.move", "action_add_from_quant", [resId, quantIds[0]]);
        await this.env.reload(this.props.record._parentRecord);
    }

    createQuant() {
        const defaultLocationId = this.byproduct
            ? this.props.production.data.production_location_id.id
            : this.props.production.data.location_src_id.id;
        return this.openQuantRecord({
            context: {
                form_view_ref: "stock.view_stock_quant_form",
                default_product_id: this.props.record.data.product_id.id,
                default_location_id: defaultLocationId,
            },
            immediate: true,
            title: _t("Create Move Line for %(product)s", {
                product: this.props.record.data.product_id.display_name,
            }),
        });
    }

    editQuantity(record) {
        this.dialog.add(MrpQuantityDialog, {
            record,
            confirm: this.env.reload.bind(this, this.props.record._parentRecord),
        });
    }
}
