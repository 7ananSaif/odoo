import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { renderToElement } from "@web/core/utils/render";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { DateSelectionPopup } from "@l10n_at_pos/app/components/popup/date_selection_popup/date_selection_popup";

patch(Navbar.prototype, {
    setup() {
        super.setup(...arguments);
        this.mapNames = {
            gross_amount_standard: _t("Gross Amount Standard"),
            gross_amount_reduced_1: _t("Gross Amount Reduced 1"),
            gross_amount_reduced_2: _t("Gross Amount Reduced 2"),
            gross_amount_special: _t("Gross Amount Special"),
            gross_amount_zero: _t("Gross Amount Zero"),
        };
    },

    get menuLabel() {
        return _t("Monthly / Yearly Receipts");
    },

    printClosingReceipts() {
        this.dialog.add(DateSelectionPopup, {
            title: _t("Print closing receipts"),
            getPayload: async (payload) => {
                const res = await this.pos.data.call(
                    "pos.config",
                    "fetch_fiskaly_closing_receipt_data",
                    [[this.pos.session.config_id.id], payload.selectedDate, payload.period]
                );
                if (res[0] && this.pos.hardwareProxy) {
                    // prepare title based on selection
                    const date = new Date(`${payload.selectedDate}-01`);
                    const monthName = date.toLocaleString("default", { month: "long" });
                    const year = date.getFullYear();
                    const title = payload.period == "monthly" ? `${monthName} ${year}` : `${year}`;

                    // prepare qrImage data
                    const codeWriter = new window.ZXing.BrowserQRCodeSvgWriter();
                    const qr_code_svg = new XMLSerializer().serializeToString(
                        codeWriter.write(res[0]["qr_code_data"], 150, 150)
                    );
                    const qrImage = "data:image/svg+xml;base64," + window.btoa(qr_code_svg);

                    const receipt = renderToElement("l10n_at_pos.ClosingReceipts", {
                        config: this.pos.session.config_id,
                        heading: title,
                        data: res[0],
                        qrImage: qrImage,
                        raw_data: res[0]["schema"]["raw"],
                        mappedName: this.mapNames,
                    });
                    const { successful, message } =
                        await this.pos.hardwareProxy.printer.printReceipt(receipt);
                    if (!successful) {
                        this.dialog.add(AlertDialog, { title: message.title, body: message.body });
                    }
                } else {
                    const msg = this.pos.hardwareProxy?.printer
                        ? _t("Fetched data is empty")
                        : _t("No printer found");
                    this.dialog.add(AlertDialog, { title: _t("Printing Error"), body: msg });
                }
            },
        });
    },
});
