import BarcodeModel from "@stock_barcode/models/barcode_model";
import { patch } from "@web/core/utils/patch";

patch(BarcodeModel.prototype, {
    showSubcontractingDetails(line) {
        return false;
    },
});
