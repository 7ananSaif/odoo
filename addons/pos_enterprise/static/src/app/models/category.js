import { PosCategory } from "@point_of_sale/app/models/pos_category";
import { patch } from "@web/core/utils/patch";

patch(PosCategory.prototype, {
    get states() {
        return this.models["pos.prep.state"].filter((state) =>
            state.categories.some((categ) => categ.id === this.id)
        );
    },
});
