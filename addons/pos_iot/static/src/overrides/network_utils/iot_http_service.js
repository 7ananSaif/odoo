import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { iotHttpService, IotHttpService } from "@iot/network_utils/iot_http_service";

patch(iotHttpService, {
    dependencies: [...iotHttpService.dependencies, "dialog"].filter(
        (dep) => dep !== "lazy_session"
    ),
});

patch(IotHttpService.prototype, {
    setup({ dialog }) {
        super.setup(...arguments);
        this.dialog = dialog;
    },

    async _longpolling() {
        try {
            return await super._longpolling(...arguments);
        } catch (error) {
            const isKiosk = !odoo.pos_config_id;
            if (error.message === "Longpolling action failed" && !isKiosk) {
                this.dialog.add(AlertDialog, {
                    title: _t("IoT Box Warning"),
                    body: _t(`It seems that your POS cannot contact your IOT through the local network. The POS will fallback with web socket connection.
You can check if all your connected devices are connected to the same network as the IoT Box.
If the problem persists, consult the documentation or contact our support.`),
                });
            }
            throw error;
        }
    },
});
