import { patch } from "@web/core/utils/patch";
import { BomOverviewComponent } from "@mrp/components/bom_overview/mrp_bom_overview";

patch(BomOverviewComponent.prototype, {
    setup() {
        super.setup();
        this.state.showOptions.ecos = false;
    },

    async getBomData() {
        const bomData = await super.getBomData();
        this.state.showOptions.ecos = bomData['has_ecos'];
        return bomData;
    },
});
