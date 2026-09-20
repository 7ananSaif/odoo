import BarcodePickingModel from "@stock_barcode/models/barcode_picking_model";
import { patch } from "@web/core/utils/patch";

patch(BarcodePickingModel.prototype, {
    showSubcontractingDetails(line) {
        return line.is_subcontract_stock_barcode && !["done", "cancel"].includes(line.state);
    },

    async _getActionSubcontractingDetails(line) {
        await this.save();
        return this.orm.call("stock.move", "action_show_subcontract_details", [
            [line.move_id],
            line.lot_id.id,
        ]);
    },
});
