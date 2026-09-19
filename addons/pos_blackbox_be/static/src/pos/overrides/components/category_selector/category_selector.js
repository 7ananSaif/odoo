import { CategorySelector } from "@point_of_sale/app/components/category_selector/category_selector";
import { patch } from "@web/core/utils/patch";

patch(CategorySelector.prototype, {
    getCategoriesAndSub() {
        const result = super.getCategoriesAndSub(...arguments);
        if (this.pos.useBlackBoxBe()) {
            const fiscal_data_category = this.pos.config.work_in_product.pos_categ_ids[0];
            return result.filter((category) => category.id !== fiscal_data_category.id);
        }
        return result;
    },
});
