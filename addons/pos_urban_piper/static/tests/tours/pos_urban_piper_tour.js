import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as Order from "@point_of_sale/../tests/generic_helpers/order_widget_util";
import * as UrbanPiper from "@pos_urban_piper/../tests/tours/utils/pos_urban_piper_utils";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import { inLeftSide } from "@point_of_sale/../tests/pos/tours/utils/common";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("OrderFlowTour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(2),
            UrbanPiper.onDropdownStatus("New"),
            UrbanPiper.orderButtonClick("Accept"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(1),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderHasText("001", "Acknowledged"),
            UrbanPiper.orderHasText("001", "Just Eat"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.onDropdownStatus("New"),
            TicketScreen.selectOrder("002"),
            UrbanPiper.orderButtonClick("Accept"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(0),
            UrbanPiper.orderHasText("002", "Acknowledged"),
            UrbanPiper.onDropdownStatus("Ongoing"),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderButtonClick("Mark as ready"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.orderHasText("001", "Food Ready"),
            TicketScreen.selectFilter("Active"),
            TicketScreen.selectOrder("002"),
            UrbanPiper.orderButtonClick("Mark as ready"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.orderHasText("002", "Food Ready"),
        ].flat(),
});

registry.category("web_tour.tours").add("OrderWithInstructionTour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(1),
            UrbanPiper.onDropdownStatus("New"),
            Order.hasCustomerNote("Make it spicy.."),
            UrbanPiper.orderButtonClick("Accept"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(0),
            UrbanPiper.orderHasText("001", "Acknowledged"),
            UrbanPiper.orderHasText("001", "Just Eat"),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderButtonClick("Mark as ready"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.orderHasText("001", "Food Ready"),
        ].flat(),
});

registry.category("web_tour.tours").add("OrderWithChargesAndDiscountTour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(1),
            UrbanPiper.onDropdownStatus("New"),
            UrbanPiper.orderButtonClick("Accept"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(0),
            UrbanPiper.orderHasText("001", "Acknowledged"),
            UrbanPiper.orderHasText("001", "Just Eat"),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderButtonClick("Mark as ready"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.orderHasText("001", "Food Ready"),
        ].flat(),
});

registry.category("web_tour.tours").add("test_payment_method_close_session", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickDisplayedProduct("Product 1"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Urban Piper"),
            PaymentScreen.clickValidate(),
            Chrome.clickMenuOption("Close Register"),
            Dialog.confirm("Close Register"),
        ].flat(),
});

registry.category("web_tour.tours").add("OrderPrepTime", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(1),
            UrbanPiper.onDropdownStatus("New"),
            UrbanPiper.clickPrepTime(),
            UrbanPiper.clickPrepTime(),
            UrbanPiper.orderButtonClick("Accept"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(0),
            UrbanPiper.orderHasText("001", "Acknowledged"),
            UrbanPiper.orderHasText("001", "Just Eat"),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderButtonClick("Mark as ready"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.orderHasText("001", "Food Ready"),
        ].flat(),
});

registry.category("web_tour.tours").add("test_reject_order", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(1),
            UrbanPiper.onDropdownStatus("New"),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderButtonClick("Reject"),
            {
                content: "select reason 'Product is out of Stock'",
                trigger: ".selection-item:contains('Product is out of Stock')",
                run: "click",
            },
        ].flat(),
});

registry.category("web_tour.tours").add("test_to_check_attribute", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(1),
            inLeftSide(
                Order.hasLine({
                    productName: "Configurable Chair",
                    quantity: 2,
                    attributeLine: "Red, Metal, Wool, Cushion, Cup Holder",
                })
            ),
            UrbanPiper.onDropdownStatus("New"),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderButtonClick("Accept"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(0),
            UrbanPiper.orderHasText("001", "Acknowledged"),
            UrbanPiper.orderHasText("001", "Just Eat"),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderButtonClick("Mark as ready"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.orderHasText("001", "Food Ready"),
        ].flat(),
});
