import { patch } from "@web/core/utils/patch";
import { hootPosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { models } from "@web/../tests/web_test_helpers";

export class AppointmentType extends models.ServerModel {
    _name = "appointment.type";
    _records = [
        {
            id: 42,
            name: "Appointment with Jethalal",
        },
    ];
}

patch(hootPosModels, [...hootPosModels, AppointmentType]);
