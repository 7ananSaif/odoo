import { Voip } from "@voip/core/voip_service";

import { patch } from "@web/core/utils/patch";

patch(Voip.prototype, {
    get transcriptionEnabled() {
        return this.transcriptionPolicy === "always" && this.mode === "prod";
    },
});
