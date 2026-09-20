import { models } from "@web/../tests/web_test_helpers";

export class PosPrepStage extends models.ServerModel {
    _name = "pos.prep.stage";

    _load_pos_preparation_data_fields() {
        return [];
    }

    _records = [
        {
            id: 1,
            name: "To prepare",
            color: "#6C757D",
            alert_timer: 10,
            prep_display_id: 1,
            write_date: "2025-10-31 15:19:30",
        },
        {
            id: 2,
            name: "Ready",
            color: "#4D89D1",
            alert_timer: 5,
            prep_display_id: 1,
            write_date: "2025-10-31 15:19:30",
        },
        {
            id: 3,
            name: "Completed",
            color: "#4ea82a",
            alert_timer: 0,
            prep_display_id: 1,
            write_date: "2025-10-31 15:19:30",
        },
    ];
}
