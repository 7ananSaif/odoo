import { expect, test } from "@odoo/hoot";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { onRpc, patchWithCleanup } from "@web/../tests/web_test_helpers";

definePosModels();

test("pos_iot_common", async () => {
    onRpc("/hw_drivers/action", () => true);
    onRpc("/iot_drivers/event", () => true);
    patchWithCleanup(console, { log: () => {} });

    // Fonts
    onRpc("/css", () => "");
    onRpc("/fonts/*", () => "");
    onRpc("/point_of_sale/static/*", () => "");
    onRpc("/web/static/*", () => "");

    const store = await setupPosEnv();
    const hardwareProxy = store.hardwareProxy;
    const iotBoxes = hardwareProxy.iotBoxes;

    // IOT box loaded correctly
    expect(iotBoxes).toHaveLength(1);
    expect(iotBoxes[0].name).toBe("DEMO IOT BOX");
    expect(iotBoxes[0].ip).toBe("1.1.1.1");
    expect(store.config.useProxy).toBe(true);

    // Connect the IOT box
    expect(hardwareProxy.iotBoxes[0].connected).toBeEmpty();
    await hardwareProxy.setProxyConnectionStatus("1.1.1.1", true);
    expect(hardwareProxy.connectionInfo.status).toBe("connected");
    expect(hardwareProxy.iotBoxes[0].connected).toBe(true);

    // Drivers are set properly
    expect(Object.keys(hardwareProxy.deviceControllers)).toEqual([
        "printer",
        "display",
        "scanners",
        "scale",
    ]);
    expect(store.scale._scaleDevice).not.toBeEmpty();

    // printer
    expect(store.unwatched.printers).toHaveLength(2); // epos in point_of_sale test data + IoT in pos_iot test data
    expect(hardwareProxy.printer).not.toBeEmpty(); // printer should be connected
    const hardwareProxyPrinter = hardwareProxy.printer.device;
    expect(hardwareProxyPrinter.id).toInclude("listener");
    expect(hardwareProxyPrinter.identifier).toBe("printer_identifier");

    // printer methods like sendPrintingJob & cashbox are not checked here as
    // iotAction is already tested in iot_http_service.test.js
    // disconnect the iot
    await hardwareProxy.setProxyConnectionStatus("1.1.1.1", false);
    expect(hardwareProxy.iotBoxes[0].connected).toBe(false);
    expect(hardwareProxy.connectionInfo.status).toBe("disconnected");
    expect(hardwareProxy.connectionInfo.message).toBe("DEMO IOT BOX disconnected");
});
