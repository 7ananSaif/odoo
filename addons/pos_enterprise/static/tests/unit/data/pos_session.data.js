import { PosSession } from "@point_of_sale/../tests/unit/data/pos_session.data";
import { patch } from "@web/core/utils/patch";

patch(PosSession.prototype, {
    _load_pos_data_models(config_id) {
        return [...super._load_pos_data_models(...arguments), "pos.prep.display"];
    },
    _load_preparation_data_models() {
        return [
            "res.company",
            "res.currency",
            "pos.config",
            "pos.category",
            "pos.prep.order",
            "pos.order",
            "pos.prep.state",
            "pos.prep.line",
            "pos.prep.stage",
            "product.product",
            "pos.preset",
            "product.attribute",
            "product.template.attribute.value",
            "resource.calendar.attendance",
            "product.attribute.custom.value",
            "pos.session",
            "pos.config",
        ];
    },
    getModelsToLoad(opts) {
        if (opts.preparation_display) {
            return this._load_preparation_data_models();
        }
        return super.getModelsToLoad(opts);
    },
    getModelFieldsToLoad(model, opts) {
        if (opts.preparation_display && model._load_pos_preparation_data_fields) {
            return model._load_pos_preparation_data_fields();
        }
        return super.getModelFieldsToLoad(model, opts);
    },
    processPosReadData(model, records, opts) {
        if (opts.preparation_display && model._post_read_pos_preparation_data) {
            return model._post_read_pos_preparation_data(records);
        }
        return super.processPosReadData(model, records, opts);
    },
});
