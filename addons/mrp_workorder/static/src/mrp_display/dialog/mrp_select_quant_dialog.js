import { useSubEnv } from "@odoo/owl";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";
import { useBus, useService } from "@web/core/utils/hooks";

export class MrpSelectQuantDialog extends SelectCreateDialog {
    static props = { ...SelectCreateDialog.props, record: Object };
    setup() {
        super.setup();
        this.barcode = useService("barcode");
        useBus(this.barcode.bus, "barcode_scanned", this._onBarcodeScanned);
        useSubEnv({
            config: {
                ...this.env.config,
                disableSearchBarAutofocus: true,
            },
        });
    }

    async _onBarcodeScanned(event) {
        if (event.detail.barcode.startsWith("OBT") || event.detail.barcode.startsWith("OCD")) {
            return;
        }
        const { model, resModel, resId } = this.props.record;
        const res = await model.orm.call(resModel, "get_quant_from_barcode", [
            [resId],
            event.detail.barcode,
        ]);
        return this.select([res]);
    }
}
