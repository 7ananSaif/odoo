import { defineModels } from "@web/../tests/web_test_helpers";
import { mailModels } from "@mail/../tests/mail_test_helpers";
import { hootPosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { PosPrepStage } from "./pos_prep_stage.data";
import { PosPrepOrder } from "./pos_prep_order.data";
import { PosPrepLine } from "./pos_prep_line.data";
import { PosPrepState } from "./pos_prep_state.data";

export const definePosPrepDisplayModels = () => {
    const hootPosPrepDisplayModels = [
        ...hootPosModels,
        PosPrepStage,
        PosPrepOrder,
        PosPrepLine,
        PosPrepState,
    ];
    const posModelNames = hootPosPrepDisplayModels.map(
        (modelClass) => modelClass.prototype.constructor._name
    );
    const modelsFromMail = Object.values(mailModels).filter(
        (modelClass) => !posModelNames.includes(modelClass.prototype.constructor._name)
    );
    defineModels([...modelsFromMail, ...hootPosPrepDisplayModels]);
};
