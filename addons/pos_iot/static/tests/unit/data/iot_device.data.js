import { patch } from "@web/core/utils/patch";
import { hootPosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { models } from "@web/../tests/web_test_helpers";

export class IotDevice extends models.ServerModel {
    _name = "iot.device";

    _load_pos_data_fields() {
        return ["iot_ip", "iot_id", "identifier", "type", "manual_measurement"];
    }

    _records = [
        {
            id: 2,
            name: "IOT Printer",
            iot_id: 2,
            identifier: "printer_identifier",
            type: "printer",
            connection: "network",
            connected_status: "disconnected",
        },
        {
            id: 3,
            name: "IOT Customer Display",
            iot_id: 2,
            identifier: "display_identifier",
            type: "display",
            connection: "hdmi",
            connected_status: "disconnected",
        },
        {
            id: 4,
            name: "IOT Barcode Scanner",
            iot_id: 2,
            identifier: "scanner_identifier",
            type: "scanner",
            connection: "direct",
            connected_status: "disconnected",
        },
        {
            id: 5,
            name: "IOT Scale",
            iot_id: 2,
            identifier: "scale_identifier",
            type: "scale",
            connection: "serial",
            connected_status: "disconnected",
        },
    ];
}

patch(hootPosModels, [...hootPosModels, IotDevice]);
