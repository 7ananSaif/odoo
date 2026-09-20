import { registry } from "@web/core/registry";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";

registry.category("web_tour.tours").add("test_ec_pos_order_refund", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            ProductScreen.clickCustomer("Deco Addict"),
            ProductScreen.clickDisplayedProduct("Desk Organizer"),
            ProductScreen.totalAmountIs("5.10"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),
            ReceiptScreen.clickNextOrder(),
            ProductScreen.clickRefund(),
            TicketScreen.search("Customer", "Deco Addict"),
            TicketScreen.selectOrder("001"),
            ProductScreen.clickNumpad("1"),
            TicketScreen.confirmRefund(),
            {
                content: `customer 'Deco Addict' is selected`,
                trigger: `button.partner-button:contains('Deco Addict')`,
            },
            Chrome.endTour(),
        ].flat(),
});
