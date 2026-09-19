import { Component, toRaw } from "@odoo/owl";

import { ActionButton } from "@voip/softphone/action_button";
import { useService } from "@web/core/utils/hooks";

export class CallBanner extends Component {
    static components = { ActionButton };
    static props = { call: Object };
    static template = "voip.CallBanner";

    setup() {
        this.userAgent = useService("voip.user_agent");
        this.softphone = useService("voip").softphone;
    }

    get contactName() {
        return this.props.call?.partner_id?.voipName || this.props.call?.phone_number || "";
    }

    get isCallOnHold() {
        return toRaw(this.userAgent.activeSession) === toRaw(this.userAgent.mainSession)
            ? this.userAgent.mainSession?.isOnHold
            : this.userAgent.transferSession?.isOnHold;
    }

    onClickHangUp() {
        this.userAgent.hangup({
            session:
                toRaw(this.userAgent.activeSession) === toRaw(this.userAgent.mainSession)
                    ? this.userAgent.transferSession
                    : this.userAgent.mainSession,
        });
    }

    onClickSwitchCall() {
        this.userAgent.activeSession.isOnHold = true;
        this.userAgent.activeSession =
            toRaw(this.userAgent.activeSession) === toRaw(this.userAgent.mainSession)
                ? this.userAgent.transferSession
                : this.userAgent.mainSession;
        this.userAgent.activeSession.isOnHold = false;
    }
}
