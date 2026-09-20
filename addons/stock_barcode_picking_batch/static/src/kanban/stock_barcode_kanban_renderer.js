import { markup, onWillStart } from "@odoo/owl";
import { StockBarcodeKanbanRenderer } from "@stock_barcode/kanban/stock_barcode_kanban_renderer";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

patch(StockBarcodeKanbanRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        this.actionService = useService("action");
        this.orm = useService("orm");
        this.activeId = this.props.list.evalContext.active_id;
        this.displayTransferProtip =
            this.displayTransferProtip || this.resModel === "stock.picking.batch";

        if (["stock.picking", "stock.picking.batch"].includes(this.resModel)) {
            onWillStart(async () => {
                const modelToSearch =
                    this.resModel === "stock.picking" ? "stock.picking.batch" : "stock.picking";
                this.otherRecordsCount = await this.orm.call(
                    "stock.picking.type",
                    "get_model_records_count",
                    [this.activeId, modelToSearch]
                );
            });
        }
    },

    async displayPickings() {
        if (this.resModel === "stock.picking") {
            return;
        }
        const action = await this.orm.call(
            "stock.picking.type",
            "get_action_picking_tree_ready_kanban",
            [this.activeId]
        );
        // markup: help is coming from HTML field on ir.actions.actions
        action.help = markup(action.help);
        return this.displayAction(action);
    },

    async displayBatches() {
        if (this.resModel === "stock.picking.batch") {
            return;
        }
        const action = await this.orm.call(
            "stock.picking.type",
            "action_picking_batch_barcode_kanban",
            [this.activeId]
        );
        // markup: help is coming from HTML field on ir.actions.actions
        action.help = markup(action.help);
        return this.displayAction(action);
    },

    displayAction(action) {
        return this.actionService.doAction(action, {
            stackPosition: "replaceCurrentAction",
            additionalContext: this.props.list.evalContext,
        });
    },
});
