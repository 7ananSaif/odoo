import { patch } from "@web/core/utils/patch";
import { hootPosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { models, MockServer } from "@web/../tests/web_test_helpers";

export class PosPrepDisplay extends models.ServerModel {
    _name = "pos.prep.display";

    _load_pos_data_fields() {
        return ["id", "category_ids", "write_date"];
    }

    _load_pos_preparation_data_fields() {
        return ["id", "category_ids", "write_date"];
    }

    load_data_params() {
        return MockServer.env["pos.session"].load_data_params({ preparation_display: true });
    }

    load_preparation_data() {
        return MockServer.env["pos.session"].load_data({ preparation_display: true });
    }

    pos_has_valid_product() {
        return true;
    }

    get_preparation_display_order() {
        return {
            "pos.prep.state": [],
            "pos.prep.order": [],
            "pos.prep.line": [],
            "pos.order": [],
            "product.product": [],
            "product.template.attribute.value": [],
            "product.attribute": [],
            "product.attribute.custom.value": [],
        };
    }

    _records = [
        {
            id: 1,
            category_ids: [1],
            write_date: "2025-07-22 15:19:30",
        },
    ];
}

patch(hootPosModels, [...hootPosModels, PosPrepDisplay]);
