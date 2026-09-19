import { registry } from "@web/core/registry";
import { Base } from "@point_of_sale/app/models/related_models";
export class PosPrepStage extends Base {
    static pythonModel = "pos.prep.stage";

    setup(vals) {
        super.setup(vals);
        this.recallHistory = [];
    }
}

registry.category("pos_available_models").add(PosPrepStage.pythonModel, PosPrepStage);
