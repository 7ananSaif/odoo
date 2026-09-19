import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class WebsiteSaleSubscriptionChangeProductPrice extends Interaction {
    static selector = ".on_change_plan_table";
    dynamicContent = {
        ".plan_select": { "t-on-change": this._onPlanChange },
        "#allow_one_time_sale": { "t-on-change": this._onBuyOnceSelected },
    };

    async _onPlanChange(e) {
        e.preventDefault();
        const buyOnceRadio = document.getElementById("allow_one_time_sale");
        const deliveryRadio = document.getElementById("regular_delivery");

        if (buyOnceRadio && deliveryRadio) {
            buyOnceRadio.checked = false;
            deliveryRadio.checked = true;
        }
    }

    async _onBuyOnceSelected(e) {
        const deliveryRadio = document.getElementById("regular_delivery");
        if (deliveryRadio) {
            deliveryRadio.checked = false;
        }

        document.querySelectorAll(".plan_select").forEach(radio => {
            radio.checked = false;
        });
    }
}

registry
    .category("public.interactions")
    .add("website_sale_subscription.change_product_price", WebsiteSaleSubscriptionChangeProductPrice);
