/* global posmodel */
export function onDropdownStatus(status) {
    return [
        {
            trigger: ".delivery-icon-container",
            run: "click",
        },
        {
            trigger: `.urbanpiper-dropdown-container .container-fluid:eq(0) span b:contains("${status}")`,
            run: "click",
        },
    ];
}

export function orderButtonClick(status) {
    return [
        {
            trigger: `.validation > span:contains("${status}")`,
            run: "click",
        },
    ];
}

export function checkNewOrderCount(expectedCount) {
    return [
        {
            trigger: `.delivery-icon-container > div:contains(${expectedCount})`,
        },
    ];
}

/**
 * Function to fetch delivery data for the POS system.
 * This function simulates the behavior of a delivery order data retrieval process
 * that integrates with the POS system. It is used to manually trigger updates when
 * webhook notifications (bus) are not functioning during tours.
 */
export function fetchDeliveryData() {
    return [
        {
            content: "Fetching Delivery order data",
            trigger: ".pos",
            run: async function () {
                /**
                 * Normally, when the POS webhook controllers receive a notification (e.g., Order placed),
                 * the POS client would be updated via the bus (real-time notification system).
                 * However, during tours or test scenarios, the bus may not function.
                 * To ensure updates occur during these scenarios, we manually trigger the method
                 * that would typically handle the callback from the bus event.
                 * This method fetches delivery-related data from the backend using the `call` method.
                 */
                const response = await posmodel.data.call(
                    "pos.config",
                    "get_delivery_data",
                    [posmodel.config.id],
                    {}
                );
                posmodel.delivery_order_count = response.delivery_order_count;
                posmodel.delivery_providers = response.delivery_providers;
                posmodel.total_new_order = response.total_new_order;
                posmodel.delivery_providers_active = response.delivery_providers_active;
            },
        },
    ];
}

export function clickPrepTime() {
    return [
        {
            trigger: `.increment-btn`,
            run: "click",
        },
    ];
}

export function orderHasText(orderNumber, text) {
    return [
        {
            trigger: `.ticket-screen .orders tbody .order-row:has(td:contains("${orderNumber}")):has(td:contains("${text}"))`,
        },
    ];
}
