import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { BlackboxError } from "@pos_blackbox_be/pos/app/utils/blackbox_error";

patch(Navbar.prototype, {
    async clock() {
        if (this.pos.useBlackBoxBe()) {
            try {
                if (!this.pos.userSessionStatus) {
                    await this.pos.clock(true);
                } else {
                    await this.pos.clock(false);
                }
            } catch (e) {
                if (e instanceof BlackboxError) {
                    e.retry = this.clock.bind(this);
                }
                throw e;
            }
        }
    },
    get workButtonName() {
        return this.pos.userSessionStatus ? "Clock out" : "Clock in";
    },
});
