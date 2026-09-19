import { _t } from "@web/core/l10n/translation";
import { markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { isDisplayStandalone } from "@web/core/browser/feature_detection";

export async function shareUrl() {
    await navigator
        .share({
            url: browser.location.href,
            title: document.title,
        })
        .catch((e) => {
            if (!(e instanceof DOMException && e.name === "AbortError")) {
                throw e;
            }
        });
}

export function shareUrlMenuItem(env) {
    return {
        type: "item",
        hide: env.isSmall || !isDisplayStandalone(),
        id: "share_url",
        description: markup`
            <div class="d-flex align-items-center justify-content-between">
                <span>${_t("Share")}</span>
                <span class="fa fa-share-alt"></span>
            </div>`,
        callback: shareUrl,
        sequence: 25,
    };
}

if (navigator.share) {
    registry.category("user_menuitems").add("share_url", shareUrlMenuItem);
}
