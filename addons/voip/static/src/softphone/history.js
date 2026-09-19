import { Component, onMounted, useState } from "@odoo/owl";

import { tabComponents } from "@voip/softphone/tab";
import { isSubstring, matchPhoneNumber } from "@voip/utils/utils";

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";

/**
 * List of your most recent calls.
 */
export class History extends Component {
    static components = tabComponents;
    static defaultProps = { extraClass: "" };
    static props = { extraClass: { type: String, optional: true } };
    static template = "voip.History";

    setup() {
        this.action = useService("action");
        this.userAgent = useService("voip.user_agent");
        this.voip = useService("voip");
        this.ui = useService("ui");
        this.softphone = useState(this.voip.softphone);
        this.state = useState(this.voip.softphone.history);
        onMounted(() => this.voip.fetchRecentCalls(this.state.searchInputValue));
        this.onInputSearch = useDebounced(
            () => this.voip.fetchRecentCalls(this.state.searchInputValue),
            300
        );
    }

    get callsByDate() {
        const calls = [...this.filteredCalls];
        calls.sort((a, b) => (b.start_date || b.create_date) - (a.start_date || a.create_date));
        const today = luxon.DateTime.now();
        const yesterday = luxon.DateTime.now().minus({ days: 1 });
        return Map.groupBy(calls, (call) => {
            const date = call.start_date || call.create_date;
            if (today.hasSame(date, "day")) {
                return _t("Today");
            }
            if (yesterday.hasSame(date, "day")) {
                return _t("Yesterday");
            }
            return date.toLocaleString(luxon.DateTime.DATE_MED);
        });
    }

    /**
     * Get the locale list of calls, filtered by search terms if available.
     */
    get filteredCalls() {
        const calls = Object.values(this.voip.calls);
        const searchTerms = this.state.searchInputValue.trim();
        if (!searchTerms) {
            return calls;
        }
        return calls.filter((call) => {
            if (call.partner_id && isSubstring(call.partner_id.name, searchTerms)) {
                return true;
            }
            return matchPhoneNumber(call.phone_number, searchTerms);
        });
    }

    getStatusColor(call) {
        const pendingCall = this.userAgent.activeSession?.call;
        switch (call.state) {
            case "rejected":
            case "missed":
                return "text-danger";
            case "calling":
            case "ongoing":
                return call.id === pendingCall?.id ? "text-muted" : "text-danger";
            case "aborted":
            case "terminated":
            default:
                return "text-muted";
        }
    }

    /** @returns {string} */
    getStatusText(call) {
        const pendingCall = this.userAgent.activeSession?.call;
        switch (call.state) {
            case "aborted":
                return _t("Cancelled call");
            case "missed":
                return _t("Missed call");
            case "rejected":
                return _t("Rejected call");
            case "terminated": {
                if (call.direction === "incoming") {
                    return _t("Incoming call (%(duration)s)", { duration: call.durationString });
                }
                return _t("Outgoing call (%(duration)s)", { duration: call.durationString });
            }
            case "calling":
                return call.eq(pendingCall) ? _t("Trying to call") : _t("Ended unexpectedly");
            case "ongoing":
                return call.eq(pendingCall) ? _t("Ongoing") : _t("Ended unexpectedly");
            default:
                return "✌︎☹︎☹︎☜︎💧︎ ✋︎💧︎ 😐︎✌︎🏱︎⚐︎❄︎";
        }
    }

    getSubtitleIcon(call) {
        const classes = ["oi oi-fw"];
        if (call.direction === "incoming") {
            classes.push("oi-arrow-down-left");
        } else {
            classes.push("oi-arrow-up-right");
        }
        const pendingCall = this.userAgent.activeSession?.call;
        switch (call.state) {
            case "terminated":
                classes.push("text-success");
                break;
            case "rejected":
            case "missed":
                classes.push("text-danger");
                break;
            case "calling":
            case "ongoing":
                classes.push(call.id === pendingCall?.id ? "text-muted" : "text-danger");
                break;
            case "aborted":
            default:
                classes.push("text-muted");
                break;
        }
        return classes.join(" ");
    }

    onClickActivity(call) {
        const action = {
            type: "ir.actions.act_window",
            res_id: false,
            res_model: "mail.activity",
            views: [[false, "form"]],
            view_mode: "form",
            target: "new",
            context: {
                default_activity_type_id: this.voip.callActivityTypeId,
            },
        };
        if (call.partner_id) {
            action.context.default_res_id = call.partner_id.id;
            action.context.default_res_model = "res.partner";
        }
        this.action.doAction(action);
    }

    onClickCall(call) {
        this.userAgent.makeCall({ partner: call.partner_id, phone_number: call.phone_number });
    }

    onClickContact(call) {
        const action = {
            type: "ir.actions.act_window",
            res_model: "res.partner",
            views: [[false, "form"]],
            target: this.ui.isSmall ? "new" : "current",
            context: {},
        };
        if (call.partner_id) {
            action.res_id = call.partner_id.id;
        } else {
            action.context.default_phone = call.phone_number;
        }
        this.action.doAction(action);
    }

    onClickEmail(call) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "mail.compose.message",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_res_ids: [call.partner_id.id],
                default_model: "res.partner",
                default_partner_ids: [call.partner_id.id],
                default_composition_mode: "comment",
                default_use_template: true,
            },
        });
    }

    openPartnerList() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Contacts",
            res_model: "res.partner",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            target: this.ui.isSmall ? "new" : "current",
        });
    }

    /** @param {MouseEvent} ev */
    onClickExpandHistory(ev) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Recent Calls"),
            res_model: "voip.call",
            target: this.ui.isSmall ? "new" : "current",
            views: [
                [false, "list"],
                [false, "graph"],
                [false, "pivot"],
                [false, "form"],
            ],
            context: {
                search_default_my_calls: 1,
            },
        });
    }
}
