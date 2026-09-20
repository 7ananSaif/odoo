import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";
import { RPCError } from "@web/core/network/rpc";

patch(ClosePosPopup.prototype, {
    async closeSession() {
        try {
            if (this.pos.useBlackBoxBe()) {
                try {
                    await this.pos.data.call("pos.session", "check_everyone_is_clocked_out", [
                        this.pos.session.id,
                    ]);
                } catch (error) {
                    if (error instanceof RPCError) {
                        const inszs = await this.pos.data.call("pos.session", "get_insz_clocked", [
                            this.pos.session.id,
                        ]);
                        await this.pos.clock(false, inszs);
                    } else {
                        throw error;
                    }
                }
            }
            const result = await super.closeSession();
            if (result === false && this.pos.useBlackBoxBe() && !this.pos.userSessionStatus) {
                await this.pos.clock(true);
            }
            return result;
        } catch (error) {
            if (this.pos.useBlackBoxBe() && !this.pos.userSessionStatus) {
                await this.pos.clock(true);
            }
            throw error;
        }
    },
});
