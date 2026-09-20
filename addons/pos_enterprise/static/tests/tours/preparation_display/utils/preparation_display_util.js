export function hasOrderCard({
    orderNumber,
    productName,
    quantity,
    cancelledQty,
    note,
    comboLine,
}) {
    let trigger = `.o_pdis_order_card`;
    if (orderNumber) {
        trigger += `:has(.o_pdis_tracking_number:contains("${orderNumber}"))`;
    }
    if (productName) {
        trigger += `:has(.o_pdis_product-name:contains("${productName}"))`;
    }
    if (quantity) {
        quantity = parseFloat(quantity) % 1 === 0 ? parseInt(quantity).toString() : quantity;
        trigger += `:has(.o_pdis_todo:contains("${quantity}x"))`;
    }
    if (cancelledQty) {
        cancelledQty =
            parseFloat(cancelledQty) % 1 === 0 ? parseInt(cancelledQty).toString() : cancelledQty;
        trigger += `:has(.o_pdis--cancelled:contains("${cancelledQty}x"))`;
    }
    if (note) {
        trigger += `:has(.o_tag_badge_text:contains("${note}"))`;
    }
    if (Array.isArray(comboLine)) {
        comboLine.forEach((line) => {
            trigger += `:has(.o_preparation_display_orderline.ms-4.fst-italic .o_pdis_product-name:contains("${line}"))`;
        });
    } else if (comboLine) {
        trigger += `:has(.o_preparation_display_orderline.ms-4.fst-italic .o_pdis_product-name:contains("${comboLine}"))`;
    }
    const args = JSON.stringify(arguments[0]);
    return [
        {
            content: `Check order card with attributes: ${args}`,
            trigger,
        },
    ];
}

export function setStage(stageName) {
    return [
        {
            content: `change stage '${stageName}'`,
            trigger: `.o_pdis_navbar_stage:contains("${stageName}")`,
            run: "click",
        },
        {
            content: `Current stage '${stageName}'`,
            trigger: `.o_pdis_navbar_stage.selected:contains("${stageName}")`,
        },
    ];
}

export function clickOrder(orderNumber) {
    return [
        {
            content: `Click on order with number: ${orderNumber}`,
            trigger: `.o_pdis_order_card_header:has(.o_pdis_tracking_number:contains("${orderNumber}")`,
            run: "click",
        },
    ];
}

export function clickOrderline(orderNumber, productName) {
    return [
        {
            content: `Click on orderline with order number: ${orderNumber} and product name ${productName}`,
            trigger: `.o_pdis_order_card:has(.o_pdis_tracking_number:contains("${orderNumber}")) .o_preparation_display_orderline:has(.o_pdis_product-name:contains("${productName}"))`,
            run: "click",
        },
    ];
}

export function isStrickedOrderline(orderNumber, productName) {
    return [
        {
            content: `Check if orderline stricked with order number: ${orderNumber} and product name ${productName}`,
            trigger: `.o_pdis_order_card:has(.o_pdis_tracking_number:contains("${orderNumber}")) .o_preparation_display_orderline:has(.o_pdis_product-name:contains("${productName}").text-decoration-line-through)`,
        },
    ];
}

export function clickRecall() {
    return [
        {
            content: "Click on the Recall button",
            trigger: `.btn.btn-light:contains("Recall")`,
            run: "click",
        },
    ];
}

export function clearFilterButton() {
    return [
        {
            content: "Click on the Clear Filter button",
            trigger: `.btn.btn-info:contains("Clear All Filter")`,
            run: "click",
        },
    ];
}

export function clickFilterButton() {
    return [
        {
            content: "Click on the Filter button",
            trigger: `.btn.position-relative.h-100.px-4.rounded-0.border-end.shadow-none`,
            run: "click",
        },
    ];
}

export function checkOrderCardCount(n) {
    return {
        content: `Check that there is ${n} order cards displayed`,
        trigger: ".o_pdis_orders",
        run: function () {
            const count = document.querySelectorAll(".o_pdis_orders .o_pdis_order_card").length;
            if (count !== n) {
                throw new Error(`Expected ${n} order cards, but found ${count}.`);
            }
        },
    };
}

export function clickFilterName(name) {
    return {
        trigger: `.o_pdis_sidebar span:contains("${name}")`,
        run: "click",
    };
}
