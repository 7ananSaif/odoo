import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onWillUnmount } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";


export class AddIoTBoxFormController extends FormController {
    setup() {
        super.setup();
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.iotBoxesBeforeConnection = [];
        this.newIoTBoxes = [];              // List of new IoT boxes found
        this.iotCheckTimer = null;          // Timer to manage polling

        onMounted(async () => {
            await this.initializeIoTConnection();
        });

        onWillUnmount(() => {
            this.onWillUnmount();
        });
    }

    /**
     * Creates a loop to check for new IoT Boxes every 10 seconds.
     * @returns {Promise<void>}
     */
    async initializeIoTConnection() {
        this.iotBoxesBeforeConnection = await this.orm.call("iot.box", "search_read", [[], ["identifier"]]);

        // Set a timer to check for new IoT Boxes every 5 seconds
        this.iotCheckTimer = setInterval(async () => {
            if (await this.lookForNewIoTBox()) {
                this.notifyIoTBoxFound(true);
                clearInterval(this.iotCheckTimer);
            }
        }, 5000);

        // Set a timeout to stop the polling after 2 minutes
        setTimeout(() => this.notifyIoTBoxFound(false), 60 * 2 * 1000);
    }

    /**
     * Look for new IoT Boxes that have been connected since the last check.
     * @returns {Promise<boolean>} True if a new IoT Box has been found, false otherwise.
     */
    async lookForNewIoTBox() {
        const iotBoxesAfterConnection = await this.orm.call("iot.box", "search_read", [[], ["identifier"]]);
        this.newIoTBoxes = iotBoxesAfterConnection.filter(
            (afterBox) => !this.iotBoxesBeforeConnection.some(
                beforeBox => beforeBox.identifier === afterBox.identifier
            )
        );

        return this.newIoTBoxes.length > 0;
    }

    /**
     * Notify the user if a new IoT Box has been found. If no new IoT Box has been found, notify the user.
     * @param {boolean} found Whether a new IoT Box has been found.
     */
    notifyIoTBoxFound(found) {
        if (found) {
            this.env.services.action.doAction({ type: "ir.actions.act_window_close" });
            this.notification.add(_t("New IoT Box connected!"), { type: "success" });
        }
    }

    /**
     * Clear the timer when the component is unmounted.
     */
    onWillUnmount() {
        if (this.iotCheckTimer) {
            clearInterval(this.iotCheckTimer);
        }
    }
}

export const addIoTBox = { ...formView, Controller: AddIoTBoxFormController };

registry.category("views").add('add_iot_box_wizard', addIoTBox);
