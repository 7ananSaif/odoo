import { patch } from "@web/core/utils/patch";
import { hootPosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { models } from "@web/../tests/web_test_helpers";

export class IotChannel extends models.ServerModel {
    _name = "iot.channel";

    get_iot_channel() {
        return "test channel";
    }
    send_message() {
        return "test message";
    }
    _load_pos_data_fields() {
        return [];
    }
}

patch(hootPosModels, [...hootPosModels, IotChannel]);
