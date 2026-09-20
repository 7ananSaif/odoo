import { patch } from "@web/core/utils/patch";
import { hootPosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { models } from "@web/../tests/web_test_helpers";

export class IotBox extends models.ServerModel {
    _name = "iot.box";

    _load_pos_data_fields() {
        return ["ip", "ip_url", "name"];
    }

    _records = [
        {
            id: 2,
            name: "DEMO IOT BOX",
            identifier: "11:11:11:11:11:11",
            ip: "1.1.1.1",
            version: "25.04",
        },
    ];
}

patch(hootPosModels, [...hootPosModels, IotBox]);
