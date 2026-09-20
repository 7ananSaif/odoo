import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

export class SubscriptionCloseSelect extends Interaction {
    static selector = "#subscription-close-select";

    dynamicSelectors = {
        ...this.dynamicSelectors,
        _tooltip: () => document.querySelector(".tooltip-wrapper"),
        _retainButton: () => document.querySelector(".subscription-close-init-retain"),
        _noRetainButton: () => document.querySelector(".subscription-close-init-noretain"),
        _messages: () =>
            document.querySelectorAll(".subscription-close-message, .subscription-close-link"),
    };

    dynamicContent = {
        _root: {
            "t-on-change": this.onChange,
        },
        _retainButton: {
            "t-att-class": () => ({ "d-none": this.reasonId ? !this.hasRetention : true }),
        },
        _noRetainButton: {
            "t-att-class": () =>
                this.reasonId
                    ? { disabled: this.hasRetention, "d-none": this.hasRetention }
                    : { disabled: true, "d-none": false },
        },
        _tooltip: {
            "t-att-data-tooltip": () => {
                return this.reasonId ? "" : _t("Choose a closing reason before submitting");
            },
        },
        _messages: {
            "t-att-class": (message) => ({
                "d-none": message.dataset.id !== this.reasonId,
            }),
        },
    };

    setup() {
        this.hasRetention = false;
        this.reasonId = null;
    }

    onChange() {
        this.reasonId = this.el.value;
        this.hasRetention = false;

        if (this.reasonId) {
            const selectedOptionEl = this.el.querySelector("option:checked");
            this.hasRetention = selectedOptionEl?.dataset.retention;
        }
    }
}

registry
    .category("public.interactions")
    .add("sale_subscription.subscription_close_select", SubscriptionCloseSelect);
