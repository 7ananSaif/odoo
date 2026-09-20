import * as PrepDisplay from "@pos_enterprise/../tests/tours/preparation_display/utils/preparation_display_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("PreparationDisplayFrontEndCancelTour", {
    steps: () =>
        [
            PrepDisplay.hasOrderCard({
                orderNumber: "T4",
                productName: "Minute Maid",
                quantity: 0,
                cancelledQty: 1,
            }),
        ].flat(),
});

registry.category("web_tour.tours").add("PreparationDisplayFrontEndNoteTour", {
    steps: () =>
        [
            PrepDisplay.hasOrderCard({
                orderNumber: "T5",
                productName: "Coca-Cola",
                quantity: 1,
                note: "Test Internal Notes",
            }),
        ].flat(),
});
