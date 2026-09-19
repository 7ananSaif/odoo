import { PrepDisplay } from "@pos_enterprise/app/services/preparation_display_service";
import { patch } from "@web/core/utils/patch";

patch(PrepDisplay.prototype, {
    async setup(...args) {
        await super.setup(...args);
        this.onNotified("PAPER_STATUS", (posConfigChange) => {
            const posConfig = this.data.models["pos.config"].get(posConfigChange.id);
            if (posConfig) {
                posConfig.has_paper = posConfigChange.has_paper;
            }
        });
    },
});
