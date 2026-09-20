import { models } from "@web/../tests/web_test_helpers";

export class PosPrepOrder extends models.ServerModel {
    _name = "pos.prep.order";

    _load_pos_preparation_data_fields() {
        return [];
    }
}
