import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { ManualBarcodeScanner } from "@barcodes/components/manual_barcode";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { markup, onWillStart } from "@odoo/owl";

export class StockBarcodeKanbanRenderer extends KanbanRenderer {
    static template = "stock_barcode.KanbanRenderer";
    setup() {
        super.setup(...arguments);
        this.barcodeService = useService("barcode");
        this.dialogService = useService("dialog");
        this.resModel = this.props.list.model.config.resModel;
        this.displayTransferProtip = this.resModel === "stock.picking";
        onWillStart(this.onWillStart);
    }

    openManualBarcodeDialog() {
        this.dialogService.add(ManualBarcodeScanner, {
            facingMode: "environment",
            onResult: (barcode) => {
                this.barcodeService.bus.trigger("barcode_scanned", { barcode });
            },
            onError: () => {},
        });
    }

    async onWillStart() {
        const groups = ["stock.group_tracking_lot", "stock.group_production_lot", "uom.group_uom"];
        const hasGroups = await Promise.all(groups.map((g) => user.hasGroup(g)));
        this.packageEnabled = hasGroups[0];
        this.trackingEnabled = hasGroups[1];
        this.uomEnabled = hasGroups[2];
    }

    get transferTip() {
        const tags = { bold_s: markup`<b>`, bold_e: markup`</b>` };

        if (this.trackingEnabled) {
            if (this.packageEnabled) {
                if (this.uomEnabled) {
                    return _t(
                        "Scan a %(bold_s)s transfer%(bold_e)s, a %(bold_s)s product%(bold_e)s, a %(bold_s)s lot%(bold_e)s, a %(bold_s)s packaging%(bold_e)s, or a %(bold_s)s package%(bold_e)s to filter your records",
                        tags
                    );
                }
                return _t(
                    "Scan a %(bold_s)s transfer%(bold_e)s, a %(bold_s)s product%(bold_e)s, a %(bold_s)s lot%(bold_e)s, or a %(bold_s)s package%(bold_e)s to filter your records",
                    tags
                );
            } else if (this.uomEnabled) {
                return _t(
                    "Scan a %(bold_s)s transfer%(bold_e)s, a %(bold_s)s product%(bold_e)s, a %(bold_s)s lot%(bold_e)s, or a %(bold_s)s packaging%(bold_e)s to filter your records",
                    tags
                );
            }
            return _t(
                "Scan a %(bold_s)s transfer%(bold_e)s, a %(bold_s)s product%(bold_e)s, or a %(bold_s)s lot%(bold_e)s to filter your records",
                tags
            );
        } else if (this.packageEnabled) {
            if (this.uomEnabled) {
                return _t(
                    "Scan a %(bold_s)s transfer%(bold_e)s, a %(bold_s)s product%(bold_e)s, a %(bold_s)s packaging%(bold_e)s, or a %(bold_s)s package%(bold_e)s to filter your records",
                    tags
                );
            }
            return _t(
                "Scan a %(bold_s)s transfer%(bold_e)s, a %(bold_s)s product%(bold_e)s, or a %(bold_s)s package%(bold_e)s to filter your records",
                tags
            );
        } else if (this.uomEnabled) {
            return _t(
                "Scan a %(bold_s)s transfer%(bold_e)s, a %(bold_s)s product%(bold_e)s, or a %(bold_s)s packaging%(bold_e)s to filter your records",
                tags
            );
        }
        return _t(
            "Scan a %(bold_s)s transfer%(bold_e)s or a %(bold_s)s product%(bold_e)s to filter your records",
            tags
        );
    }
}
