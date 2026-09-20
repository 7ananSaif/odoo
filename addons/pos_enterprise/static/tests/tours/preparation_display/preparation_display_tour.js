import * as PrepDisplay from "@pos_enterprise/../tests/tours/preparation_display/utils/preparation_display_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("PreparationDisplayFrontEndTour", {
    steps: () =>
        [
            PrepDisplay.hasOrderCard({
                orderNumber: "001",
                productName: "Office Combo",
                quantity: 1,
                comboLine: ["Combo Product 3", "Combo Product 5", "Combo Product 7"],
            }),
            PrepDisplay.clickOrderline("001", "Combo Product 3"),
            PrepDisplay.isStrickedOrderline("001", "Combo Product 3"),
            PrepDisplay.clickOrder("001"),
            PrepDisplay.setStage("Ready"),
            PrepDisplay.hasOrderCard({
                orderNumber: "001",
                productName: "Office Combo",
                quantity: 1,
                comboLine: "Combo Product 3",
            }),

            PrepDisplay.setStage("To prepare"),
            PrepDisplay.clickRecall(),
            PrepDisplay.hasOrderCard({
                orderNumber: "001",
                productName: "Office Combo",
                quantity: 1,
                comboLine: ["Combo Product 3", "Combo Product 5", "Combo Product 7"],
            }),
        ].flat(),
});

registry.category("web_tour.tours").add("PreparationDisplayFilterTour", {
    steps: () =>
        [
            // By default, no filter selected so you see all orders
            PrepDisplay.hasOrderCard({ productName: "Desk Pad" }),
            PrepDisplay.hasOrderCard({ productName: "Letter Tray" }),
            PrepDisplay.hasOrderCard({ productName: "Whiteboard Pen" }),
            PrepDisplay.checkOrderCardCount(3),
            //Test time filters
            PrepDisplay.clickFilterButton(),
            PrepDisplay.clickFilterName("Today"),
            PrepDisplay.checkOrderCardCount(2),
            PrepDisplay.clickFilterName("Next days"),
            PrepDisplay.checkOrderCardCount(3),
            PrepDisplay.clearFilterButton(),
            PrepDisplay.checkOrderCardCount(3),
            // Test reset filters
            PrepDisplay.clickFilterName("Eat in"),
            PrepDisplay.checkOrderCardCount(1),
            PrepDisplay.clickFilterName("Takeaway"),
            PrepDisplay.checkOrderCardCount(2),
            PrepDisplay.clickFilterName("Delivery"),
            PrepDisplay.checkOrderCardCount(3),
            PrepDisplay.clearFilterButton(),
            // Test product filters
            PrepDisplay.clickFilterName("Desk Pad"),
            PrepDisplay.checkOrderCardCount(1),
            PrepDisplay.clickFilterName("Letter Tray"),
            PrepDisplay.checkOrderCardCount(2),
            PrepDisplay.clickFilterName("Whiteboard Pen"),
            PrepDisplay.checkOrderCardCount(3),
            PrepDisplay.clearFilterButton(),
            // Test product category filters
            PrepDisplay.clickFilterName("Desk test"),
            PrepDisplay.checkOrderCardCount(1),
            PrepDisplay.clearFilterButton(),
            // Mix filters
            PrepDisplay.clickFilterName("Eat in"),
            PrepDisplay.clickFilterName("Takeaway"),
            PrepDisplay.checkOrderCardCount(2),
            PrepDisplay.clickFilterName("Next days"),
            PrepDisplay.checkOrderCardCount(1),
            PrepDisplay.clickFilterName("Today"),
            PrepDisplay.checkOrderCardCount(2),
            PrepDisplay.clickFilterName("Desk Pad"),
            PrepDisplay.checkOrderCardCount(1),
            PrepDisplay.clearFilterButton(),
        ].flat(),
});
