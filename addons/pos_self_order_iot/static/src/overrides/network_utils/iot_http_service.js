import { patch } from "@web/core/utils/patch";
import { IotHttpService, iotHttpService } from "@iot/network_utils/iot_http_service";
import { rpc } from "@web/core/network/rpc";
import { browser } from "@web/core/browser/browser";

patch(IotHttpService.prototype, {
    async getIotBoxData(iotBoxId) {
        const access_token = new URLSearchParams(browser.location.search).get("access_token");
        const record = await rpc("/pos-self-order/get-iot-box-data/", {
            access_token,
            iot_box_id: iotBoxId,
        });
        if (record.error) {
            throw new Error(record.error);
        }
        return record;
    },
});

patch(iotHttpService, {
    dependencies: iotHttpService.dependencies.filter((dep) => dep !== "orm"),
});
