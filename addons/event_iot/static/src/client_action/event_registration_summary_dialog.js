import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { EventRegistrationSummaryDialog } from "@event/client_action/event_registration_summary_dialog";
import { onMounted, useState } from "@odoo/owl";

const PRINT_SETTINGS_LOCAL_STORAGE_KEY = "event.registration_print_settings";
const DEFAULT_PRINT_SETTINGS = {
    autoPrint: false,
    iotPrinterId: null,
};

patch(EventRegistrationSummaryDialog.prototype, {
    setup() {
        super.setup();
        this.iotHttpService = useService("iot_http");

        const storedPrintSettings = browser.localStorage.getItem(PRINT_SETTINGS_LOCAL_STORAGE_KEY);
        this.printSettings = useState(
            storedPrintSettings ? JSON.parse(storedPrintSettings) : DEFAULT_PRINT_SETTINGS
        );
        this.useIotPrinter = this.registration.iot_printers.length > 0;

        if (
            this.useIotPrinter &&
            !this.registration.iot_printers
                .map((printer) => printer.id)
                .includes(this.printSettings.iotPrinterId)
        ) {
            this.printSettings.iotPrinterId = null;
        }

        if (this.registration.iot_printers.length === 1) {
            this.printSettings.iotPrinterId = this.registration.iot_printers[0].id;
        }

        this.dialogState = useState({ isHidden: this.willAutoPrint });

        onMounted(() => {
            if (
                this.willAutoPrint &&
                ![
                    "already_registered",
                    "need_manual_confirmation",
                    "not_ongoing_event",
                    "canceled_registration",
                ].includes(this.props.registration.status)
            ) {
                this.onRegistrationPrintPdf().catch(() => {
                    this.dialogState.isHidden = false;
                });
            }
        });
    },

    get selectedPrinter() {
        return this.registration.iot_printers.find(
            (printer) => printer.id === this.printSettings.iotPrinterId
        );
    },

    get willAutoPrint() {
        return (
            this.registration.status === "confirmed_registration" &&
            this.printSettings.autoPrint &&
            this.useIotPrinter &&
            this.hasSelectedPrinter()
        );
    },

    async onRegistrationPrintPdf() {
        if (this.useIotPrinter && this.printSettings.iotPrinterId) {
            await this.printWithBadgePrinter();
            if (this.props.doNextScan) {
                this.onScanNext();
            } else {
                this.dialogState.isHidden = false;
            }
        } else {
            return super.onRegistrationPrintPdf();
        }
    },

    hasSelectedPrinter() {
        return !this.useIotPrinter || this.printSettings.iotPrinterId != null;
    },

    savePrintSettings() {
        browser.localStorage.setItem(
            PRINT_SETTINGS_LOCAL_STORAGE_KEY,
            JSON.stringify(this.printSettings)
        );
    },

    async printWithBadgePrinter() {
        const reportName = "event_iot.event_registration_badge_printer_report";
        const [{ id: reportId }] = await this.orm.searchRead(
            "ir.actions.report",
            [["report_name", "=", reportName]],
            ["id"]
        );
        const ticketType = this.registration.ticket_name ? this.registration.ticket_name : "";

        this.notification.add(
            _t("'%(name)s' %(type)s badge sent to printer '%(printer)s'", {
                name: this.registration.name,
                type: ticketType,
                printer: this.selectedPrinter.name,
            }),
            { type: "info" }
        );
        const [{ iotBoxId, document }] = await this.orm.call(
            "ir.actions.report",
            "render_document",
            [reportId, [this.selectedPrinter.id], [this.registration.id], null]
        );
        this.iotHttpService.action(iotBoxId, this.selectedPrinter.identifier, {
            document,
        });
    },
});
