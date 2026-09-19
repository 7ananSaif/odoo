import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PartnerList from "@point_of_sale/../tests/pos/tours/utils/partner_list_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import * as Utils from "@point_of_sale/../tests/pos/tours/utils/common";
import { negateStep } from "@point_of_sale/../tests/generic_helpers/utils";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("pos_settle_account_due", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            PartnerList.settleCustomerAccount("Partner Test 1", "10", "TSJ/", "/00001", true),
            ProductScreen.clickPartnerButton(),
            // Confirm that same invoice shouldn't be in the list again
            PartnerList.settleCustomerAccount(
                "Partner Test 1",
                "10",
                "TSJ/",
                "/00001",
                true,
                false,
                false
            ),
            Dialog.cancel(),
            // On cancelling it will remove customer as well
            ProductScreen.clickPartnerButton(),
            ProductScreen.clickCustomer("Partner Test 1"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickValidate(),
            Chrome.confirmPopup(),
            {
                content: "Receipt doesn't include Empty State",
                trigger: ".pos-receipt:not(:has(i.fa-shopping-cart))",
            },
            ReceiptScreen.isShown(),
            ReceiptScreen.receiptIsThere(),
            ReceiptScreen.containsOrderLine(
                `TSJ/${new Date().getFullYear()}/00001`,
                0,
                "10.00",
                "0.00"
            ),
            ReceiptScreen.receiptAmountTotalIs("0.00"),
            ReceiptScreen.paymentLineContains("Bank", "10.00"),
            ReceiptScreen.paymentLineContains("Customer Account", "-10.00"),
            Chrome.endTour(),
        ].flat(),
});

registry.category("web_tour.tours").add("SettleDueButtonPresent", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            PartnerList.clickPartnerOptions("A Partner"),
            PartnerList.checkDropDownItemText("Deposit money"),
            PartnerList.clickPartnerOptions("B Partner"),
            PartnerList.checkDropDownItemText("Settle orders"),
        ].flat(),
});

registry.category("web_tour.tours").add("pos_settle_account_due_update_instantly", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            ProductScreen.clickCustomer("A Partner"),
            ProductScreen.addOrderline("Desk Pad", "10"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Customer Account"),
            PaymentScreen.clickValidate(),
            ReceiptScreen.receiptIsThere(),
            ReceiptScreen.paymentLineContains("Customer Account", "19.80"),
            ReceiptScreen.clickNextOrder(),
            ProductScreen.clickPartnerButton(),
            PartnerList.settleCustomerAccount(
                "A Partner",
                "19.80",
                "Shop - 000001",
                "",
                false,
                true
            ),
            ProductScreen.clickPartnerButton(),
            // Confirm that same invoice shouldn't be in the list again
            PartnerList.settleCustomerAccount(
                "A Partner",
                "19.80",
                "Shop - 000001",
                "",
                false,
                true,
                false,
                false
            ),
            Dialog.cancel(),
            // On cancelling it will remove customer as well
            ProductScreen.clickPartnerButton(),
            ProductScreen.clickCustomer("A Partner"),
            ProductScreen.modeIsActive("Price"),
            ProductScreen.clickNumpad("1", "0"),
            ProductScreen.totalAmountIs("10.00"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickValidate(),
            Dialog.confirm("Yes"),
            ReceiptScreen.clickNextOrder(),
            ProductScreen.clickPartnerButton(),
            PartnerList.settleCustomerAccount(
                "A Partner",
                "9.80",
                "Shop - 000001",
                "",
                false,
                true
            ),
            ProductScreen.totalAmountIs("9.80"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickInvoiceButton(),
            PaymentScreen.clickValidate(),
            Dialog.confirm("Yes"),
            ReceiptScreen.clickNextOrder(),
            ProductScreen.clickPartnerButton(),
            PartnerList.clickPartnerOptions("A Partner"),
            // Deposit money should be shown (since we have no more due to settle)
            PartnerList.checkDropDownItemText("Deposit money"),
            PartnerList.clickDropDownItemText("Deposit money"),
            Dialog.is("Select the payment method to deposit money"),
            Utils.selectButton("Bank"),
            PaymentScreen.clickValidate(),
            Dialog.bodyIs("You can not deposit zero amount."),
            Dialog.confirm(),
            Chrome.endTour(),
        ].flat(),
});

registry.category("web_tour.tours").add("test_settle_order_partially_backend_01", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            ProductScreen.clickCustomer("A Partner"),
            ProductScreen.addOrderline("Desk Pad", "10"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Customer Account"),
            PaymentScreen.clickInvoiceButton(),
            PaymentScreen.clickValidate(),
            ReceiptScreen.clickNextOrder(),
            ProductScreen.clickPartnerButton(),
            PartnerList.settleCustomerAccount("A Partner", "19.80", "TSJ/", "/00001", true),
            ProductScreen.modeIsActive("Price"),
            ProductScreen.clickNumpad("1", "0"),
            ProductScreen.totalAmountIs("10.00"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickValidate(),
            Dialog.confirm("Yes"),
            ReceiptScreen.clickNextOrder(),
            Chrome.endTour(),
        ].flat(),
});

registry.category("web_tour.tours").add("test_settle_order_partially_backend_02", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            PartnerList.settleCustomerAccount("A Partner", "4.80", "TSJ/", "/00001", true),
            ProductScreen.totalAmountIs("4.80"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickValidate(),
            Dialog.confirm("Yes"),
            ReceiptScreen.clickNextOrder(),
            Chrome.endTour(),
        ].flat(),
});

registry.category("web_tour.tours").add("test_settle_due_account_ui_coherency_2", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            PartnerList.clickPartnerOptions("B Partner"),
            negateStep(PartnerList.checkDropDownItemText("Deposit money")),
        ].flat(),
});

registry.category("web_tour.tours").add("SettleDueAmountMoreCustomers", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            PartnerList.searchCustomerValue("BPartner", true),
            {
                trigger: ".partner-line-balance:contains('10.00')",
                run: () => {},
            },
        ].flat(),
});

registry.category("web_tour.tours").add("pos_settle_open_invoice", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            PartnerList.clickPartnerOptions("C partner"),
            {
                isActive: ["auto"],
                trigger: "div.o_popover :contains('Settle invoices')",
                content: "Check the popover opened",
                run: "click",
            },
            {
                trigger: "tr.o_data_row td[name='name']:contains('INV/2025/00001')",
                content: "Check the invoice is present",
                run: "click",
            },
            ProductScreen.clickNumpad("5"),
            ProductScreen.selectedOrderlineHas("INV", 1, "5"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickValidate(),
            Utils.selectButton("Yes"),
            ReceiptScreen.receiptIsThere(),
            ReceiptScreen.containsOrderLine("INV/2025/00001", 0, "5.00", "0.00"),
            ReceiptScreen.receiptAmountTotalIs("0.00"),
            ReceiptScreen.paymentLineContains("Bank", "5.00"),
            ReceiptScreen.paymentLineContains("Customer Account", "-5.00"),
            Chrome.endTour(),
        ].flat(),
});

registry.category("web_tour.tours").add("pos_settle_open_invoice_with_credit_note", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),

            ProductScreen.clickPartnerButton(),
            PartnerList.clickPartnerOptions("C Partner"),
            {
                trigger: "div.o_popover :contains('Settle invoices')",
                content: "Open settle invoices from partner dropdown",
                run: "click",
            },
            {
                trigger: "thead .o_list_record_selector input",
                content: "Click 'Select All' checkbox to select both invoice and credit note",
                run: "click",
            },
            {
                trigger: "tr.o_data_row td[name='name']:contains('INV/2025/00001')",
                content: "Invoice is present in the settle dialog",
            },
            {
                trigger: "tr.o_data_row td[name='name']:contains('RINV/2025/00001')",
                content: "Credit note is present in the settle dialog",
            },
            {
                trigger: ".modal-footer button:contains('Select')",
                content: "Confirm selection of invoice and credit note",
                run: "click",
            },
            ProductScreen.totalAmountIs("8.00"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickValidate(),
            Utils.selectButton("Yes"),

            ReceiptScreen.receiptIsThere(),
            ReceiptScreen.receiptAmountTotalIs("0.00"),
            ReceiptScreen.paymentLineContains("Bank", "8.00"),
            ReceiptScreen.paymentLineContains("Customer Account", "-8.00"),

            Chrome.endTour(),
        ].flat(),
});
