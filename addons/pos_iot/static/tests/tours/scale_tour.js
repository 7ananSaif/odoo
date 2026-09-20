/* global posmodel */

import { registry } from "@web/core/registry";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";

class PosScaleDummy {
    manual_measurement = false;
    iotId = 1;
    identifier = "scale_1";
}

class IotHttpServiceDummy {
    action() {}
    onMessage(_iotBoxId, _deviceIdentifier, onSuccess) {
        setTimeout(
            () =>
                onSuccess({
                    status: { status: "connected" },
                    result: 2.35,
                }),
            1000
        );
        return Promise.resolve();
    }
}

registry.category("web_tour.tours").add("pos_iot_scale_tour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            {
                content: "mock the connected scale",
                trigger: ".pos .pos-content",
                run: function () {
                    posmodel.hardwareProxy.deviceControllers.scale = new PosScaleDummy();
                    posmodel.scale.iotHttpService = new IotHttpServiceDummy();
                },
            },
            ProductScreen.clickDisplayedProduct("Whiteboard Pen"),
            {
                content: "gross weight is set",
                trigger: '.gross-weight:contains("2.35")',
            },
            {
                content: "total price is correct",
                trigger: '.computed-price:contains("7.52")',
            },
            {
                content: "confirm the weighing",
                trigger: ".buy-product",
                run: "click",
            },
            ProductScreen.selectedOrderlineHas("Whiteboard Pen", "2.35"),
        ].flat(),
});
