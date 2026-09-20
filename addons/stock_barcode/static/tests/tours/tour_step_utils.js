export const stepUtils = {
    confirmAddingUnreservedProduct() {
        return [
            {
                trigger: ".modal:not(.o_inactive_modal) .modal-title:contains(Add extra product?)",
            },
            {
                trigger: ".modal:not(.o_inactive_modal) .btn-primary",
                run: "click",
            },
            {
                trigger: "body:not(:has(.modal))",
            },
        ];
    },
    inputManuallyBarcode(barcode) {
        return [
            { trigger: ".o_barcode_actions", run: "click" },
            { trigger: "input#manual_barcode", run: "click" },
            { trigger: "input#manual_barcode", run: `edit ${barcode}` },
            { trigger: "input#manual_barcode+button", run: "click" },
        ];
    },
    validateBarcodeOperation(trigger = ".o_barcode_client_action .o_barcode_lines") {
        return [
            {
                trigger: "body:not(:has(.modal))",
            },
            {
                trigger,
                run: "scan OBTVALI",
            },
            {
                trigger: ".o_notification_bar.bg-success",
            },
        ];
    },
    discardBarcodeForm() {
        return [
            {
                isActive: ["auto"],
                content: "discard barcode form",
                trigger: ".o_discard",
                run: "click",
            },
            {
                content: "wait to be back on the barcode lines",
                trigger: ".o_add_line",
            },
        ];
    },
    /**
     * Check notification's message. Assume the tested message is the first one (more recent)
     * and also close the notification by default (see `close` parameter.)
     * @param {string} message The exact notification's message
     * @param {boolean} [close=true]
     * @returns {Array}
     */
    checkNotificationMessage(message, close = true) {
        const baseSelector = ".o_notification_manager .o_notification:first-child";
        const steps = [
            {
                content: "Check notification's message",
                trigger: `${baseSelector} .o_notification_content:text('${message}')`,
            },
        ];
        if (close) {
            steps.push({
                content: "Close the notification",
                trigger: `${baseSelector} button.o_notification_close`,
                run: "click",
            });
        }
        return steps;
    },
    // RFID utils.
    countUniqRFID(count) {
        return [{ trigger: `.o_barcode_count_rfid .o_rfid_unique_tags:contains(${count})` }];
    },
    countTotalRFID(count) {
        return [{ trigger: `.o_barcode_count_rfid .o_rfid_total_read:contains(${count})` }];
    },
    closeCountRFID() {
        return [{ trigger: ".o_barcode_count_rfid button.btn-close" }];
    },
};
