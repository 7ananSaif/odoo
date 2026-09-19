import { patch } from "@web/core/utils/patch";
import { PosStore, posService } from "@point_of_sale/app/services/pos_store";
import { isFiscalPrinterActive } from "./helpers/utils";

patch(posService, {
    dependencies: [...posService.dependencies, "epson_fiscal_printer"],
});

patch(PosStore.prototype, {
    async setup(env, { epson_fiscal_printer }) {
        await super.setup(...arguments);
        if (isFiscalPrinterActive(this.config)) {
            const { it_fiscal_printer_https, it_fiscal_printer_ip } = this.config;
            this.fiscalPrinter = epson_fiscal_printer(
                it_fiscal_printer_https,
                it_fiscal_printer_ip
            );
            this.fiscalPrinter.getPrinterSerialNumber().then((sn) => {
                this.config.it_fiscal_printer_serial_number = sn;
            });
        }
    },
    getSyncAllOrdersContext(orders, options = {}) {
        const context = super.getSyncAllOrdersContext(orders, options);
        if (isFiscalPrinterActive(this.config)) {
            // No need to slow down the order syncing by generating the PDF in the server.
            // The invoice will be printed by the fiscal printer.
            context["generate_pdf"] = false;
        }
        return context;
    },
    // override
    async printReceipt({
        basic = false,
        order = this.getOrder(),
        printBillActionTriggered = false,
    } = {}) {
        if (!isFiscalPrinterActive(this.config)) {
            return super.printReceipt(...arguments);
        }

        if (!order.nb_print) {
            const result = order.to_invoice
                ? await this.fiscalPrinter.printFiscalInvoice()
                : await this.fiscalPrinter.printFiscalReceipt();

            if (result.success) {
                this.data.write("pos.order", [order.id], {
                    it_fiscal_receipt_number: result.addInfo.fiscalReceiptNumber,
                    it_fiscal_receipt_date: result.addInfo.fiscalReceiptDate,
                    it_z_rep_number: result.addInfo.zRepNumber,
                    //update the number of times the order got printed, handling undefined
                    nb_print: order.nb_print ? order.nb_print + 1 : 1,
                });
                if (this.config.it_fiscal_cash_drawer) {
                    await this.fiscalPrinter.openCashDrawer();
                }
                return true;
            }
        } else {
            this.fiscalPrinter.printContentByNumbers({
                order: order,
            });
        }
    },
});
