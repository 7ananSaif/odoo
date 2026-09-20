import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { logPosMessage } from "@point_of_sale/app/utils/pretty_console_log";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { cookie } from "@web/core/browser/cookie";
import mobile from "@web_mobile/js/services/core";

patch(Navbar.prototype, {
    setup() {
        super.setup();
        if (this.supportDualDisplay) {
            mobile.methods.getDisplays({ onlyPresentation: true }).then((result) => {
                if (!result.success || !result.data) {
                    return;
                }
                /**
                 * @typedef {Object} Display
                 * @property {number} displayId - The ID of the display.
                 * @property {string} name - The name of the display.
                 */

                /** @type {Display[]} */
                const displays = result.data;
                const customerDisplayId = cookie.get("pos_customer_display_id");
                displays.forEach((display) => {
                    if (customerDisplayId && display.displayId.toString() === customerDisplayId) {
                        this._showDisplayAndGoToUrl({ displayId: display.displayId });
                    } else {
                        mobile.methods
                            .showDisplayAndGoToUrl({
                                url: "about:blank",
                                displayId: display.displayId,
                            })
                            .catch((error) => {
                                logPosMessage(
                                    "Navbar",
                                    "setup",
                                    "Error opening customer display",
                                    false,
                                    [error]
                                );
                            });
                    }
                });
            });
        }
    },
    get supportDualDisplay() {
        return mobile.methods.getDisplays;
    },
    openCustomerDisplay() {
        if (!this.supportDualDisplay) {
            super.openCustomerDisplay();
            return;
        }
        mobile.methods
            .getDisplays({ onlyPresentation: true })
            .then((result) => {
                if (!result.success || !result.data) {
                    this.notification.add(_t("Dual display is not supported on this device"));
                    return;
                }

                /**
                 * @typedef {Object} Display
                 * @property {number} displayId - The ID of the display.
                 * @property {string} name - The name of the display.
                 */

                /** @type {Display[]} */
                const displays = result.data;
                if (displays.length === 1) {
                    this._showDisplayAndGoToUrl({ displayId: displays[0].displayId });
                } else {
                    makeAwaitable(this.dialog, SelectionPopup, {
                        list: displays.map((display) => ({
                            id: display.displayId,
                            label: display.name,
                            isSelected: false,
                            item: display,
                        })),
                        title: _t("Select a display"),
                    }).then((selectedDisplay) => {
                        if (!selectedDisplay) {
                            return;
                        }
                        this._showDisplayAndGoToUrl({
                            displayId: selectedDisplay.displayId,
                        });
                    });
                }
            })
            .catch((error) => {
                logPosMessage(
                    "Navbar",
                    "openCustomerDisplay",
                    "Error opening customer display",
                    false,
                    [error]
                );
                this.notification.add(_t("An error occurred while opening the display."));
            });
    },
    _showDisplayAndGoToUrl({ displayId }) {
        cookie.set("pos_customer_display_id", displayId);
        mobile.methods
            .showDisplayAndGoToUrl({
                url: `${this.pos.config._base_url}/pos_customer_display/${this.pos.config.id}/${this.pos.config.access_token}`,
                displayId: displayId,
            })
            .catch((error) => {
                logPosMessage(
                    "Navbar",
                    "_showDisplayAndGoToUrl",
                    "Error opening customer display",
                    false,
                    [error]
                );
                this.notification.add(_t("An error occurred while opening the display."));
            });
    },
});
