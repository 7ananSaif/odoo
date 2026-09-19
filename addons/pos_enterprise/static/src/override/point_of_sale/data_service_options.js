import { DataServiceOptions } from "@point_of_sale/app/models/data_service_options";
import { patch } from "@web/core/utils/patch";

patch(DataServiceOptions.prototype, {
    get dynamicModels() {
        const models = super.dynamicModels;
        return ["pos.prep.display", ...models];
    },
});
