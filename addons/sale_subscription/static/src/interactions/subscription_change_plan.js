import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class SubscriptionChangePlan extends Interaction {
    static selector = ".o_portal_sale_sidebar";

    start() {
        if (new URLSearchParams(window.location.search).get("change_plan") === "true") {
            document.getElementById("o_change_plan")?.click();
        }
    }
}

registry
    .category("public.interactions")
    .add("sale_subscription.subscription_change_plan", SubscriptionChangePlan);
