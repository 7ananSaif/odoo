import { _t } from "@web/core/l10n/translation";
import { registry } from '@web/core/registry';
import { IotActionButton } from "./iot_action_button/iot_action_button";


export class IotPictureWidget extends IotActionButton {
    async onClick() {
        const { iotBoxId, deviceIdentifier } = this.iotDevice;
        this.notification.add(_t('Capturing image...'));
        this.iotHttpService.action(
            iotBoxId,
            deviceIdentifier,
            {},
            this.onSuccess.bind(this),
            this.notifyFailure.bind(this)
        );
    }

    notifyFailure() {
        this.notification.add(_t('Failed to take a picture using the IoT Camera'), {
            type: 'danger',
        });
    }

    async onSuccess(data) {
        if (!data.result?.image) {
            return this.notifyFailure();
        }
        this.notification.add(_t("Image captured successfully"), { type: 'success' });
        this.props.record.update({ picture: data.result?.image });
    }
}

registry.category("view_widgets").add("iot_picture", {
    component: IotPictureWidget,
    extractProps: ({ attrs }) => {
        return { btn_name: attrs.btn_name };
    },
});
