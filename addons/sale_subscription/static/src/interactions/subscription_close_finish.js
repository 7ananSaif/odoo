import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class SubscriptionCloseFinish extends Interaction {
    static selector = ".subscription-close-finish";
    dynamicContent = {
        _root: {
            "t-on-click": this.onClick,
        },
    };

    onClick() {
        this.el.setAttribute("disabled", "true");
        const spinner = document.createElement("i");
        spinner.classList.add("fa", "fa-circle-o-notch", "fa-spin");
        this.insert(spinner, this.el, "afterbegin");
        document.querySelector("#wc-modal-close-init form").submit();
    }
}

registry
    .category("public.interactions")
    .add("sale_subscription.subscription_close_finish", SubscriptionCloseFinish);
