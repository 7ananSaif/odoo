import { _t } from "@web/core/l10n/translation";
import { BasePrinter } from "@point_of_sale/app/utils/printer/base_printer";
import { PRINTER_MESSAGES } from "@iot/network_utils/iot_http_service";
/**
 * Used to send print requests to the IoT box through the provided `device` - a `DeviceController` instance.
 */
export class IoTPrinter extends BasePrinter {
    setup({ device, iot_http }) {
        super.setup(...arguments);
        this.device = device;
        this.iotBox = iot_http;
    }

    /**
     * @override
     */
    openCashbox() {
        return this.action({ action: "cashbox" });
    }

    /**
     * @override
     */
    sendPrintingJob(img, actionId) {
        return this.action({ action: "print_receipt", receipt: img }, actionId);
    }

    async action(data, actionId = null) {
        return new Promise((resolve) => {
            const processResult = (printResult) => {
                if (printResult.status === "success") {
                    resolve(true);
                }
                resolve({
                    ...printResult,
                    result: false, // used to make the pos call ``getResultsError``
                });
            };

            this.iotBox.action(
                this.device.iotId,
                this.device.identifier,
                data,
                processResult,
                processResult,
                actionId
            );
        });
    }

    /**
     * @override
     */
    getActionError() {
        if (window.isSecureContext && this.device.iotIp.endsWith(".odoo-iot.com")) {
            return {
                successful: false,
                canRetry: true,
                message: {
                    title: _t("Connection to IoT Box failed"),
                    body: _t(
                        "Your IoT box is registered, but your browser could not reach it.\n" +
                            "Ensure it is powered on and connected to the network.\n\n" +
                            "If you have just paired the IoT box, you may be experiencing a DNS issue.\n" +
                            "If you wait for some time the problem may resolve itself."
                    ),
                },
            };
        }
        return super.getActionError();
    }

    /**
     * @override
     */
    getResultsError(printResult) {
        let title = _t("Printing failed");
        let body;
        switch (printResult.status) {
            case "disconnected":
                body = _t(
                    "The IoT Box is connected, but the receipt printer isn't. In order to continue," +
                        " ensure your printer is connected:\n\n" +
                        "1/ for USB printers, check the cable between the IoT Box and the receipt printer\n" +
                        "2/ for network printers, ensure the printer is connected to the internet."
                );
                break;
            case "warning":
                // e.g. "low_paper"
                title = _t("Printing warning");
                body = PRINTER_MESSAGES[printResult.message] ?? printResult.message;
                break;
            default:
                body = PRINTER_MESSAGES[printResult.message] ?? printResult.message;
                break;
        }
        return {
            successful: false,
            canRetry: printResult.status !== "warning",
            message: { title, body },
        };
    }
}
