import * as Order from "@point_of_sale/../tests/generic_helpers/order_widget_util";

export function doubleClickLine(productName, quantity = "1") {
    return [
        ...Order.hasLine({
            run: "dblclick",
            productName,
            quantity,
        }),
    ].flat();
}
