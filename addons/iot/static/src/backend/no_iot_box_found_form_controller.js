import { discoverIotBoxes } from "@iot/client_action/discover_iot_boxes";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { registry } from "@web/core/registry";
import { onMounted, onWillUnmount } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";


export class NoIoTBoxFoundFormController extends FormController {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.retryDiscoverInterval = null;

        onMounted(() => {
            this.startCountdown(15);
        });

        onWillUnmount(() => {
            if (this.retryDiscoverInterval) {
                clearInterval(this.retryDiscoverInterval);
            }
        });
    }

    /**
     * Create and show a countdown. When it reaches 0 we look for new IoT Boxes again
     */
    startCountdown(seconds) {
        const countdownSpinner = document.getElementById("discover_retry_spinner");
        const countdownEl = document.getElementById("discover_retry_countdown");
        const textToDisplay = _t("Retrying in ")
        let timeLeft = seconds;
        if (countdownEl) {
            countdownEl.textContent = `${textToDisplay}${timeLeft}s`;
            this.retryDiscoverInterval = setInterval(async () => {
                timeLeft--;
                countdownEl.textContent = `${textToDisplay}${timeLeft}s`;
                // Look for new IoT Boxes again
                if (timeLeft <= 0) {
                    countdownEl.textContent = `${textToDisplay}0s`;
                    const nextAction = await discoverIotBoxes(this.env)
                    if (!nextAction.no_iot_found_found) {
                        await this.actionService.doAction(nextAction);
                    }
                    timeLeft = seconds + 1;
                }
            }, 1000);
        }
        // Clear the countdown and interval
        setTimeout(() => {
            if (countdownEl) {
                countdownSpinner.classList.add("o_hidden");
                countdownEl.textContent = null;
                clearInterval(this.retryDiscoverInterval);
            }
        }, 60 * 5 * 1000);
    }
}

export const noIoTBoxFound = { ...formView, Controller: NoIoTBoxFoundFormController };

registry.category("views").add('no_iot_box_found_wizard', noIoTBoxFound);
