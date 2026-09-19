import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as PartnerList from "@point_of_sale/../tests/pos/tours/utils/partner_list_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("l10n_pe_edi_pos.RefundWithReasonTour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickDisplayedProduct("Desk Organizer", true, "1.0", "5.10"),
            ProductScreen.clickPartnerButton(),
            PartnerList.searchCustomerValue("company_1_data", true),
            PartnerList.clickPartner("company_1_data"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),
            ReceiptScreen.isShown(),
            Chrome.clickOrders(),
            TicketScreen.selectFilter("Active"),
            TicketScreen.selectFilter("Paid"),
            TicketScreen.selectOrder("0001"),
            TicketScreen.confirmRefund(),
            // Additional Refund Information Dialog
            Dialog.confirm("Ok"),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),
            ReceiptScreen.isShown(),
            Chrome.endTour(),
        ].flat(),
});
