import { Component } from "@odoo/owl";

import { Call } from "@voip/core/call_model";
import { ActionButton } from "@voip/softphone/action_button";
import { ContactInfo } from "@voip/softphone/contact_info";

import { useService } from "@web/core/utils/hooks";

/**
 * Incoming call screen. Displays information about the caller, along with a
 * series of actions, and buttons to accept or reject the call.
 */
export class CallInvitation extends Component {
    static components = { ActionButton, ContactInfo };
    static props = { call: Call };
    static template = "voip.CallInvitation";

    setup() {
        this.action = useService("action");
        this.userAgent = useService("voip.user_agent");
        this.voip = useService("voip");
        this.ui = useService("ui");
    }

    /** @param {MouseEvent} ev */
    onClickAccept(ev) {
        this.userAgent.acceptIncomingCall();
    }

    /** @param {MouseEvent} ev */
    onClickActivity(ev) {
        const action = {
            type: "ir.actions.act_window",
            res_id: false,
            res_model: "mail.activity",
            views: [[false, "form"]],
            view_mode: "form",
            target: this.ui.isSmall ? "new" : "current",
            context: {
                default_activity_type_id: this.voip.callActivityTypeId,
            },
        };
        if (this.props.call.partner_id) {
            Object.assign(action.context, {
                default_res_id: this.props.call.partner_id.id,
                default_res_model: "res.partner",
            });
        }
        this.action.doAction(action);
    }

    /** @param {MouseEvent} ev */
    onClickContact(ev) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: this.props.call.partner_id.id,
            views: [[false, "form"]],
            target: this.ui.isSmall ? "new" : "current",
        });
    }

    /** @param {MouseEvent} ev */
    onClickReject(ev) {
        this.userAgent.rejectIncomingCall();
    }
}
