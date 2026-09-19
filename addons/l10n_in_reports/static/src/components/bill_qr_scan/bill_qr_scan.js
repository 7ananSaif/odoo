import {
    AccountMoveKanbanController,
} from "@account/views/account_move_kanban/account_move_kanban_controller";
import {
    AccountMoveListController,
} from "@account/views/account_move_list/account_move_list_controller";
import { Component, onWillStart, useSubEnv } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { isBarcodeScannerSupported } from "@web/core/barcode/barcode_video_scanner";
import { ManualBarcodeScanner } from "@barcodes/components/manual_barcode";
import { user } from "@web/core/user";

export class BillQrScan extends Component {

    static template = "l10n_in_reports.billScanInput";
    static components = { Dialog };
    static props = { close: Function };

    setup() {
        this.actionService = useService('action');
        this.notificationService = useService("notification");
        this.barcodeService = useService('barcode');
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        useBus(this.barcodeService.bus, "barcode_scanned", (ev) => this._onBarcodeScanned(ev));
        onWillStart(async () => {
            this.isMobileScanner = isBarcodeScannerSupported();
        });
    }

    async openMobileScanner() {
        this.dialog.add(ManualBarcodeScanner, {
            facingMode: "environment",
            onResult: (barcode) => {
                if (barcode) {
                    this.barcodeService.bus.trigger("barcode_scanned", { barcode });
                    if ("vibrate" in window.navigator) {
                        window.navigator.vibrate(100);
                    }
                } else {
                    this.env.services.notification.add(_t("Please, Scan again!"), {
                        type: "warning",
                    });
                }
            },
            placeholder: _t("Enter QR / IRN Manually"),
            onError: () => {},
        });
    }

    async _onBarcodeScanned(ev) {
        this.env.services.ui.block();
        try {
            const res = await this.orm.call(
                "account.move", "l10n_in_get_bill_from_qr_raw", [], { qr_raw: ev?.detail?.barcode }
            );
            if (res.action) {
                return this.actionService.doAction(res.action);
            }
            this.notificationService.add(res.warning, { type: "warning" });
        } finally {
            this.env.services.ui.unblock();
        }
    }
}
registry.category('actions').add('l10n_in_bill_qr_code_scan', BillQrScan);

export function qrBillScannerController() {
    return {
        setup() {
            super.setup();
            this.dialog = useService("dialog");
            this.orm = useService("orm");
            useSubEnv({
                openScanWizard: this.openScanWizard.bind(this),
            });
            onWillStart(async () => {
                const currentCompanyId = user.activeCompany.id;
                this.data = await this.orm.searchRead("res.company", [["id", "=", currentCompanyId]], ["country_code"])
                this.countryCode = this.data[0].country_code;
            });
        },
    
        openScanWizard() {
            this.dialog.add(BillQrScan);
        },

        get isButtonDisplayed() {
            return this.countryCode == 'IN' && ["in_invoice", "in_refund"].includes(this.props.context.default_move_type ?? '')
        },
    }
}

patch(AccountMoveKanbanController.prototype, qrBillScannerController());
patch(AccountMoveListController.prototype, qrBillScannerController());
