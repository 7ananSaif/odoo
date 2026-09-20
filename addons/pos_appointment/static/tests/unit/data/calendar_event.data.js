import { patch } from "@web/core/utils/patch";
import { hootPosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { models } from "@web/../tests/web_test_helpers";

export class CalendarEvent extends models.ServerModel {
    _name = "calendar.event";

    _load_pos_data_fields() {
        return [
            "id",
            "start",
            "duration",
            "stop",
            "name",
            "appointment_type_id",
            "appointment_status",
            "appointment_resource_ids",
            "total_capacity_reserved",
        ];
    }
}

patch(hootPosModels, [...hootPosModels, CalendarEvent]);
