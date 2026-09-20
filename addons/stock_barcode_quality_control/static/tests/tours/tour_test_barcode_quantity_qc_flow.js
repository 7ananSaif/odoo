import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("test_operation_quality_check_barcode", {
    steps: () => [
        {
            trigger: ".o_button_operations",
            run: "click",
        },
        {
            trigger: ".o_barcode_picking_type:contains(Receipts)",
            run: "click",
        },
        {
            trigger: "button.o-kanban-button-new",
            run: "click",
        },
        {
            trigger: ".o_barcode_lines",
            run: "scan product1",
        },
        {
            trigger: ".fa-pencil",
            run: "click",
        },
        {
            trigger: ".o_digipad_increment",
            run: "click",
        },
        {
            trigger: ".o_save",
            run: "click",
        },
        {
            trigger: ".o_barcode_lines",
            run() {},
        },
        {
            trigger: ".o_barcode_lines",
            run: "scan product2",
        },
        {
            trigger:
                ".o_barcode_line:has(.o_barcode_line_title:contains(product2)) button.o_add_quantity",
            run: "click",
        },
        {
            trigger: ".o_validate_page",
            run: "click",
        },
        {
            trigger: ".modal-content:has(.modal-header:contains(product 1)) button[name=do_pass]",
            run: "click",
        },
        {
            trigger: ".modal-content:has(.modal-header:contains(product 2)) button[name=do_fail]",
            run: "click",
        },
        {
            trigger: ".o_notification_bar.bg-success",
            run() {},
        },
        /* Now test Quality check button appears on footer after clicking X on QC */
        {
            trigger: "button.o-kanban-button-new",
            run: "click",
        },
        {
            trigger: ".o_barcode_lines",
            run: "scan product3",
        },
        { trigger: ".o_barcode_line" },
        {
            trigger: ".o_validate_page",
            run: "click",
        },
        {
            content: "Close the QC wizard without passing or failing",
            trigger: ".modal-content button.btn-close",
            run: "click",
        },
        {
            content: "Check QC button is on footer",
            trigger: "button.o_check_quality",
        },
    ],
});

registry.category("web_tour.tours").add("test_operation_quality_check_delivery_barcode", {
    steps: () => [
        {
            trigger: ".o_button_operations",
            run: "click",
        },
        {
            trigger: ".o_kanban_record:contains('Delivery')",
            run: "click",
        },
        {
            trigger: "button.o-kanban-button-new",
            run: "click",
        },
        {
            trigger: ".o_barcode_lines",
            run: "scan product1",
        },
        {
            trigger: ".fa-pencil",
            run: "click",
        },
        {
            trigger: ".o_digipad_increment",
            run: "click",
        },
        {
            trigger: ".o_save",
            run: "click",
        },
        {
            trigger: ".o_barcode_lines",
            run() {},
        },
        {
            trigger: ".o_barcode_lines",
            run: "scan product2",
        },
        {
            trigger:
                ".o_barcode_line:has(.o_barcode_line_title:contains(product2)) button.o_add_quantity",
            run: "click",
        },
        {
            trigger: ".o_validate_page",
            run: "click",
        },
        {
            trigger: ".modal-content:has(.modal-header:contains(product 1)) button[name=do_pass]",
            run: "click",
        },
        {
            trigger: ".modal-content:has(.modal-header:contains(product 2)) button[name=do_fail]",
            run: "click",
        },
        {
            trigger: ".o_notification_bar.bg-success",
            run() {},
        },
    ],
});

registry.category("web_tour.tours").add("test_quality_check_partial_reception_barcode", {
    steps: () => [
        {
            trigger: ".o_stock_barcode_main_menu",
            run: "scan WHINQCPRB",
        },
        {
            trigger: ".o_check_quality",
            run: "click",
        },
        {
            trigger:
                ".modal-content:contains(product1):has(.o_field_widget[name=nb_checks]:contains(1)) .btn-close",
            run: "click",
        },
        {
            trigger: ".o_barcode_client_action",
            run: "scan productserial1",
        },
        {
            trigger: ".o_barcode_line.o_selected:contains(productserial1)",
            run: "scan SN001",
        },
        {
            trigger: ".o_barcode_line:contains(SN001)",
        },
        // Open QC's to check that only the one related to SN001 is todo
        {
            trigger: ".o_check_quality",
            run: "click",
        },
        // Discard the dialog and check that the validation process displays the same QC
        {
            trigger: ".modal-content:has(.modal-header:contains(productserial1)) .btn-close",
            run: "click",
        },
        {
            trigger: ".o_validate_page",
            run: "click",
        },
        {
            trigger:
                ".modal-content:has(.modal-header:contains('Incomplete Transfer')) button:contains(Validate)",
            run: "click",
        },
        {
            trigger:
                ".modal-content:has(.modal-header:contains(productserial1)) button[name=do_pass]",
            run: "click",
        },
        {
            trigger: ".o_notification_bar.bg-success",
        },
    ],
});
