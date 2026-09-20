import { OpeningControlPopup } from "@point_of_sale/app/components/popups/opening_control_popup/opening_control_popup";
import { patch } from "@web/core/utils/patch";
import { useAsyncLockedMethod } from "@point_of_sale/app/hooks/hooks";
import { useService } from "@web/core/utils/hooks";

patch(OpeningControlPopup.prototype, {
    setup() {
        super.setup();
        this.confirm = useAsyncLockedMethod(this.confirm);
        this.dialog = useService("dialog");
    },
    async confirm() {
        await super.confirm();
        if (this.pos.useBlackBoxBe() && !this.pos.userSessionStatus) {
            await this.pos.clock(true);
        }
    },
});
