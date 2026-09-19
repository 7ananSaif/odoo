import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as combo from "@point_of_sale/../tests/pos/tours/utils/combo_popup_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("PreparationDisplayTour", {
    steps: () =>
        [
            // First order should send these orderlines to preparation:
            // - Letter Tray x10
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),

            ProductScreen.addOrderline("Letter Tray", "10"),
            ProductScreen.selectedOrderlineHas("Letter Tray", "10"),
            ProductScreen.addOrderline("Magnetic Board", "5"),
            ProductScreen.selectedOrderlineHas("Magnetic Board", "5"),
            ProductScreen.addOrderline("Monitor Stand", "1"),
            ProductScreen.selectedOrderlineHas("Monitor Stand", "1"),
            ProductScreen.clickPayButton(),

            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.remainingIs("0.0"),
            PaymentScreen.validateButtonIsHighlighted(true),
            PaymentScreen.clickValidate(),

            ReceiptScreen.clickNextOrder(),

            // Should not send anything to preparation
            ProductScreen.addOrderline("Magnetic Board", "5"),
            ProductScreen.selectedOrderlineHas("Magnetic Board", "5"),
            ProductScreen.addOrderline("Monitor Stand", "1"),
            ProductScreen.selectedOrderlineHas("Monitor Stand", "1"),
            ProductScreen.clickPayButton(),

            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.remainingIs("0.0"),
            PaymentScreen.validateButtonIsHighlighted(true),
            PaymentScreen.clickValidate(),

            ReceiptScreen.clickNextOrder(),
        ].flat(),
});

registry.category("web_tour.tours").add("PreparationDisplayPrinterTour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.addOrderline("Letter Tray"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickValidate(),
            //This steps is making sure that we atleast tried to call the printer
            Dialog.is({ title: "Printing failed" }),
        ].flat(),
});

registry.category("web_tour.tours").add("PreparationDisplayTourConfigurableProduct", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickDisplayedProduct("Configurable Chair"),
            Dialog.confirm(),
            ProductScreen.addCustomerNote("Test customer note - orderline"),
            ProductScreen.totalAmountIs("11.0"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.remainingIs("0.0"),
            PaymentScreen.validateButtonIsHighlighted(true),
            PaymentScreen.clickValidate(),
            ReceiptScreen.isShown(),
        ].flat(),
});

registry.category("web_tour.tours").add("MakePosOrderWithCombo", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),

            ProductScreen.clickDisplayedProduct("Office Combo"),
            combo.select("Combo Product 3"),
            combo.select("Combo Product 5"),
            combo.select("Combo Product 7"),
            Dialog.confirm(),
            ProductScreen.selectedOrderlineHasDirect("Office Combo", "1"),
            ProductScreen.clickPayButton(),

            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.remainingIs("0.0"),
            PaymentScreen.validateButtonIsHighlighted(true),
            PaymentScreen.clickValidate(),
        ].flat(),
});

registry.category("web_tour.tours").add("test_sending_order_in_preparation_should_not_sync_more", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickDisplayedProduct("Desk Organizer", true, "1.0"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickValidate(),
            ReceiptScreen.isShown(),
            ReceiptScreen.clickNextOrder(),
        ].flat(),
});

registry.category("web_tour.tours").add("PosOrderCreationTourPdis", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            // Make simple order "Eat in"
            ProductScreen.clickDisplayedProduct("Desk Pad", true, "1.0"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickValidate(),
            ReceiptScreen.clickNextOrder(),
            // Make Takeaway order for tomorrow
            ProductScreen.clickDisplayedProduct("Letter Tray", true, "1.0"),
            ProductScreen.selectPreset("Eat in", "Takeaway"),
            Chrome.selectSlotDays("6"),
            Chrome.selectPresetTimingSlotIndex("1"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickValidate(),
            ReceiptScreen.clickNextOrder(),
            // Make a Delivery order
            ProductScreen.clickDisplayedProduct("Whiteboard Pen", true, "1.0"),
            ProductScreen.selectPreset("Eat in", "Delivery"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickValidate(),
            ReceiptScreen.clickNextOrder(),
        ].flat(),
});
