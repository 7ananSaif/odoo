import BarcodePickingModel from "@stock_barcode/models/barcode_picking_model";

import { patch } from "@web/core/utils/patch";

patch(BarcodePickingModel.prototype, {
    get isValidForBarcodeLookup() {
        if (this.record.picking_type_code === "incoming") {
            return true;
        }
        return false;
    },
    _mustScanProductFirst(barcodeData) {
        return super._mustScanProductFirst(barcodeData) && !this.isValidForBarcodeLookup;
    },
});
