/* global OdooFin */
import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

import { loadJS } from "@web/core/assets";
import { post } from "@web/core/network/http_service";

export class OnlineSyncPortal extends Interaction {
    static selector = ".oe_online_sync #renew_consent_button";
    dynamicContent = {
        _root: {
            "t-on-click.prevent.withTarget": this.onRenewConsentClick,
        },
    };

    async OdooFinConnector(action) {
        // Ensure that the proxyMode is valid
        const modeRegexp = /^[a-z0-9-_]+$/i;
        if (!modeRegexp.test(action.params.proxyMode)) {
            return;
        }

        await loadJS(`https://${action.params.proxyMode}.odoofin.com/proxy/v1/odoofin_link`);

        // Create and open the iframe
        const params = {
            data: action.params,
            proxyMode: action.params.proxyMode,
            onEvent: function (event, data) {
                if (event === "success") {
                    const processUrl = `${window.location.pathname}/complete${window.location.search}`;
                    const reconnectEls = document.querySelectorAll(".js_reconnect");
                    for (const reconnectEl of reconnectEls) {
                        reconnectEl.classList.toggle("d-none");
                    }
                    post(processUrl, { csrf_token: odoo.csrf_token });
                }
            },
        };

        OdooFin.create(params);
        OdooFin.open();
    }

    /**
     * @param {PointerEvent} ev
     * @param {HTMLElement} currentTargetEl
     */
    onRenewConsentClick(ev, currentTargetEl) {
        const action = JSON.parse(currentTargetEl.getAttribute("iframe-params"));
        this.OdooFinConnector(action);
    }
}

registry
    .category("public.interactions")
    .add("account_online_synchronization.online_sync_portal", OnlineSyncPortal);
