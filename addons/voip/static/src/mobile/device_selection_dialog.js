import { Component, onWillStart, useRef } from "@odoo/owl";

import { Session } from "@voip/core/session";

import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class DeviceSelectionDialog extends Component {
    static components = { Dialog };
    static props = { close: Function };
    static template = "voip.DeviceSelectionDialog";

    setup() {
        this.devices = [];
        this.selectRef = useRef("select");
        this.userAgent = useService("voip.user_agent");
        onWillStart(async () => (this.devices = await this.getAudioInputDevices()));
    }

    get currentDeviceId() {
        return Session.preferredInputDevice;
    }

    get dialogProps() {
        return {
            title: _t("Input device selection"),
            fullscreen: true,
        };
    }

    /** @returns {Promise<{deviceId: *, label: string}[]>} */
    async getAudioInputDevices() {
        const devices = await navigator.mediaDevices.enumerateDevices();
        return devices
            .filter(({ kind }) => kind === "audioinput")
            .map((device, i) => ({
                deviceId: device.deviceId,
                label: device.label || `Device ${i + 1}`,
            }));
    }

    /** @param {MouseEvent} ev */
    onClickCancel(ev) {
        this.props.close();
    }

    /** @param {MouseEvent} ev */
    onClickConfirm(ev) {
        Session.switchInputDevice(this.selectRef.el.value);
        this.props.close();
    }
}
