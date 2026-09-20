import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";

const IOT_PROXY_DISCOVER_BOXES_ENDPOINT =
    "https://iot-proxy.odoo.com/odoo-enterprise/iot/discover-boxes";

export async function discoverIotBoxes(env) {
    const orm = env.services.orm;
    const discoveredBoxes = [];

    try {
        const response = await rpc(IOT_PROXY_DISCOVER_BOXES_ENDPOINT);
        discoveredBoxes.push(...response);
    } catch (error) {
        console.warn("Failed to retrieve local IoT boxes: " + error);
    }

    return orm.call("iot.box", "connect_iot_box", [discoveredBoxes]);
}

registry.category("actions").add("discover_iot_boxes", discoverIotBoxes);
