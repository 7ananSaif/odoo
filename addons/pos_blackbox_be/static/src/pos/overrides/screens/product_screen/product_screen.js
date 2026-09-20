import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";

patch(ProductScreen.prototype, {
    getNumpadButtons() {
        const buttons = super.getNumpadButtons();
        if (this.pos.useBlackBoxBe()) {
            for (const button of buttons) {
                if (button.value === "-") {
                    button.class = `${button.class} disabled`;
                    break;
                }
            }
        }
        return buttons;
    },
});
