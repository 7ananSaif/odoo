import { patch } from "@web/core/utils/patch";
import { accountMoveService, AccountMoveService } from "@account/services/account_move_service";
import { getSelectedPrintersForReport } from "@iot/iot_report_action";
import { uuidv4 } from "@point_of_sale/utils";

patch(AccountMoveService.prototype, {
    setup(env, services) {
        super.setup(...arguments);
        this.iotHttp = services.iot_http;
    },

    async downloadPdf(accountMoveId) {
        const [invoiceReport] = await this.orm.searchRead(
            "ir.actions.report",
            [["report_name", "=", "account.report_invoice_with_payments"]],
            ["id", "device_ids"]
        );
        if (!invoiceReport?.device_ids?.length) {
            return super.downloadPdf(...arguments);
        }

        const selectedPrinters = await getSelectedPrintersForReport(invoiceReport.id, this.env);
        if (!selectedPrinters) {
            return super.downloadPdf(...arguments);
        }

        const downloadAction = await this.orm.call("account.move", "action_invoice_download_pdf", [
            accountMoveId,
        ]);
        const pdfResponse = await fetch(downloadAction.url);
        const pdfBytes = new Uint8Array(await pdfResponse.arrayBuffer());
        const pdfByteString = pdfBytes.reduce(
            (currentString, nextByte) => (currentString += String.fromCharCode(nextByte)),
            ""
        );
        const base64String = btoa(pdfByteString);

        const printerDevices = await this.orm.read("iot.device", selectedPrinters, [
            "iot_id",
            "identifier",
        ]);
        for (const printerDevice of printerDevices) {
            await this.iotHttp.action(printerDevice.iot_id, printerDevice.identifier, {
                document: base64String,
                print_id: uuidv4(),
            });
        }
    },
});

patch(accountMoveService, {
    dependencies: [...accountMoveService.dependencies, "iot_http"],
});
