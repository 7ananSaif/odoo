import { PrinterService } from "@point_of_sale/app/services/printer_service";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

patch(PrinterService.prototype, {
    async print(component, props, options = {}) {
        try {
            if (options && options.blackboxPrint) {
                this.blackboxPrint = true;
            }
            return await super.print(...arguments);
        } finally {
            this.blackboxPrint = false;
        }
    },
    printWeb(el) {
        if (this.blackboxPrint) {
            this.dialog.add(AlertDialog, {
                title: _t("Fiscal data module error"),
                body: _t(
                    "You're not allowed to download a ticket when using the blackbox. Please connect a printer to print the ticket."
                ),
            });
            return false;
        }
        return super.printWeb(...arguments);
    },
});
