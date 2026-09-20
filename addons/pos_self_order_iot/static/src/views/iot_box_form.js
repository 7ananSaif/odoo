import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { uniqueId } from "@web/core/utils/functions";

class IoTBoxController extends formView.Controller {
    setup() {
        super.setup();
        this.notification = useService("notification");
        this.longpolling = useService("iot_longpolling");
    }

    async onWillSaveRecord(record) {
        if (!record.data.can_be_kiosk) {
            return;
        }

        const { name, ip, screen_orientation } = record.data;
        this.longpolling.addListener(ip, ["display"], uniqueId("listener-"), () => {
            this.notification.add(_t("Screen orientation updated."), {
                title: name,
                type: "success",
            });
        });
        await this.longpolling.action(ip, "display", {
            action: "rotate_screen",
            orientation: screen_orientation,
        });
    }
}

export const iotBoxFormView = {
    ...formView,
    Controller: IoTBoxController,
};

registry.category("views").add("iot_box_form", iotBoxFormView);
