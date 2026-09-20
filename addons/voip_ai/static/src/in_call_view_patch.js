import { InCallView } from "@voip/softphone/in_call_view";

import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

patch(InCallView.prototype, {
    setup() {
        super.setup(...arguments);
        this.voip = useService("voip");
    },
    get transcriptionEnabled() {
        return this.voip.mode === "prod" && this.voip.transcriptionPolicy === "always";
    },
});
