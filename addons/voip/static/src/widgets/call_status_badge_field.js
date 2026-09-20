import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { BadgeField } from "@web/views/fields/badge/badge_field";

export class CallStatusBadgeField extends BadgeField {
    static template = "voip.CallStatusBadgeField";

    setup() {
        super.setup();
        this.userAgent = useService("voip.user_agent");
    }

    /** @returns {string} */
    get iconClass() {
        const direction = this.props.record.data.direction;
        if (direction === "outgoing") {
            return "oi oi-arrow-up-right";
        }
        if (direction === "incoming") {
            return "oi oi-arrow-down-left";
        }
        return "";
    }

    /** @returns {ReturnType<_t>} */
    get statusLabel() {
        switch (this.props.record.data.state) {
            case "missed":
                return _t("Missed Call");
            case "aborted":
                return _t("Cancelled Call");
            case "terminated":
                return this.props.record.data.direction === "incoming"
                    ? _t("Incoming call")
                    : _t("Outgoing call");
            case "rejected":
                return _t("Rejected Call");
            case "ongoing":
                return this.userAgent.activeSession?.call?.id === this.props.record.data.id
                    ? _t("Ongoing Call")
                    : _t("Ended unexpectedly");
            case "calling":
                return this.userAgent.activeSession?.call?.id === this.props.record.data.id
                    ? _t("Trying to call")
                    : _t("Ended unexpectedly");
            default:
                return _t("Unknown");
        }
    }

    /** @returns {string} */
    get badgeClass() {
        const state = this.props.record.data.state;
        if (state === "rejected" || state === "missed") {
            return "text-bg-danger";
        }
        if (state === "aborted") {
            return "text-bg-secondary";
        }
        if (state === "calling" || state === "ongoing") {
            return "text-bg-warning";
        }
        return "text-bg-success";
    }
}

registry.category("fields").add("voip_call_status_badge", {
    component: CallStatusBadgeField,
    displayName: _t("Call Status Badge"),
    supportedTypes: ["char", "selection"],
});
