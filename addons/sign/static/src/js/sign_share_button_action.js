import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

async function copyShareLinkAndCloseWizard(env, action) {
    const shareLink = action.params.share_link;
    await browser.navigator.clipboard.writeText(shareLink);
    const notificationService = env.services["notification"];
    notificationService.add(_t("Share link copied to clipboard"), {
        type: "success",
    });
    return { type: "ir.actions.act_window_close" };
}

registry.category("actions").add("sign_share_and_close_action", copyShareLinkAndCloseWizard);
