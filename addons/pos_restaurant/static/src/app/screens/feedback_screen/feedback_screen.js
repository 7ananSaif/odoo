import { FeedbackScreen } from "@point_of_sale/app/screens/feedback_screen/feedback_screen";
import { patch } from "@web/core/utils/patch";

patch(FeedbackScreen.prototype, {
    goNext() {
        if (this.isContinueSplitting()) {
            this.continueSplitting();
        } else {
            super.goNext();
        }
    },
    continueSplitting() {
        return this.pos.continueSplitting(this.currentOrder);
    },
    isContinueSplitting() {
        return this.pos.isContinueSplitting(this.currentOrder);
    },
});
