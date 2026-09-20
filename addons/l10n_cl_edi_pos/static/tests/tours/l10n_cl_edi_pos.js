/* global posmodel */

import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as PartnerList from "@point_of_sale/../tests/pos/tours/utils/partner_list_util";
import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as Notification from "@point_of_sale/../tests/generic_helpers/notification_util";
import { negate } from "@point_of_sale/../tests/generic_helpers/utils";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("test_receipt_header_content", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            ProductScreen.clickCustomer("AA Test Partner"),
            ProductScreen.clickDisplayedProduct("Desk Organizer"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickInvoiceButton(),
            PaymentScreen.clickValidate(),
            ReceiptScreen.isShown(),
            {
                trigger: ".pos-receipt .chili-ticket-info:contains('RUT: 76201224-3')",
            },
            {
                trigger: ".pos-receipt-partner:contains('RUT: 76086428-5')",
            },
        ].flat(),
});

registry.category("web_tour.tours").add("test_settle_invoice_good_price_cl", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            PartnerList.settleCustomerAccount("AA Partner SII", "20", "FAC", false),
        ].flat(),
});

registry.category("web_tour.tours").add("test_cl_receipt_dte_info", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickDisplayedProduct("Desk Organizer"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),
            ReceiptScreen.isShown(),
            {
                trigger: negate(".pos-receipt-order-data:contains('Timbre Electrónico SII')"),
            },
        ].flat(),
});

registry.category("web_tour.tours").add("test_cl_partner_missing_info", {
    steps: () =>
        [
            {
                trigger: "body",
                run: () => {
                    posmodel.editPartner = () => {
                        /* do nothing */
                    };
                },
            },
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            ProductScreen.clickCustomer("AA Test Partner"),
            ProductScreen.clickDisplayedProduct("Desk Organizer"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickInvoiceButton(),
            PaymentScreen.clickValidate(),
            Notification.has("Please fill out missing fields to proceed:"),
        ].flat(),
});

registry.category("web_tour.tours").add("test_refund_consumidor_final_anonimo", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickDisplayedProduct("Desk Organizer"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),
            ReceiptScreen.isShown(),
            ReceiptScreen.clickNextOrder(),
            ProductScreen.clickRefund(),
            TicketScreen.selectOrder("1001"),
            TicketScreen.confirmRefund(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),
            Dialog.is({ title: "Refund not possible" }),
            Dialog.bodyIs("You cannot refund orders for the Consumidor Final Anònimo."),
            Dialog.confirm(),
        ].flat(),
});
