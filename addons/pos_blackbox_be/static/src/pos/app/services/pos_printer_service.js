import { PosPrinterService } from "@point_of_sale/app/services/pos_printer_service";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

patch(PosPrinterService.prototype, {
    async printWeb() {
        if (this.blackboxPrint) {
            this.dialog.add(AlertDialog, {
                title: _t("Fiscal data module error"),
                body: _t(
                    "You're not allowed to download a ticket when using the blackbox. Please connect a printer to print the ticket."
                ),
            });
            return false;
        }
        return await super.printWeb(...arguments);
    },
});
