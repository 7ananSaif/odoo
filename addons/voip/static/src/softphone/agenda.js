import { Component, onMounted, useState } from "@odoo/owl";

import { tabComponents } from "@voip/softphone/tab";

import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";

/**
 * List of "call activities", i.e. activities of type call you were scheduled
 * to handle today.
 */
export class Agenda extends Component {
    static components = tabComponents;
    static defaultProps = { extraClass: "" };
    static props = { extraClass: { type: String, optional: true } };
    static template = "voip.Agenda";

    setup() {
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.orm = useService("orm");
        this.userAgent = useService("voip.user_agent");
        this.voip = useService("voip");
        this.ui = useService("ui");
        onMounted(() => this.voip.fetchTodayCallActivities());
        this.state = useState(this.voip.softphone.agenda);
        this.onInputSearch = useDebounced(() => this.voip.fetchTodayCallActivities(), 300);
    }

    get activitiesByDate() {
        const activities = [...this.voip.softphone.activities];
        activities.sort((a, b) => a.date_deadline - b.date_deadline);
        const today = luxon.DateTime.now();
        const yesterday = today.minus({ days: 1 });
        const tomorrow = today.plus({ days: 1 });
        return Map.groupBy(activities, (activity) => {
            const dueDate = activity.date_deadline;
            if (today.hasSame(dueDate, "day")) {
                return _t("Due: Today");
            }
            if (yesterday.hasSame(dueDate, "day")) {
                return _t("Due: Yesterday");
            }
            if (tomorrow.hasSame(dueDate, "day")) {
                return _t("Due: Tomorrow");
            }
            return _t("Due: %(date)s", {
                date: dueDate.toLocaleString(luxon.DateTime.DATE_MED),
            });
        });
    }

    getExtraClass(activity) {
        const today = luxon.DateTime.now().startOf("day");
        if (today > activity.date_deadline) {
            return "border-start border-danger border-2";
        }
        if (today.hasSame(activity.date_deadline, "day")) {
            return "border-start border-warning border-2";
        }
        return "";
    }

    getSectionStyle(activity) {
        const today = luxon.DateTime.now().startOf("day");
        if (today > activity.date_deadline) {
            return "text-danger";
        }
        if (today.hasSame(activity.date_deadline, "day")) {
            return "text-warning";
        }
        return "";
    }

    onClickActivity(activity) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: activity.res_model,
            res_id: activity.res_id,
            views: [[false, "form"]],
            target: this.ui.isSmall ? "new" : "current",
        });
    }

    onClickCall(activity) {
        const { partner, phone: phone_number } = activity;
        this.userAgent.makeCall({ activity, partner, phone_number });
    }

    onClickCancel(activity) {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Hold your horses!"),
            body: _t(
                "Are you sure you want to delete this activity? It will be lost forever! (A long time!)"
            ),
            cancel() {},
            confirm: async () => {
                await this.orm.call("mail.activity", "unlink", [[activity.id]]);
                activity.remove();
            },
            confirmLabel: _t("Yes, I know what I'm doing"),
            cancelLabel: _t("Missclicked, sorry"),
        });
    }

    onClickContact(partnerId) {
        if (!partnerId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: partnerId,
            views: [[false, "form"]],
            target: this.ui.isSmall ? "new" : "current",
        });
    }

    async onClickDone(activity) {
        await activity.markAsDone();
        activity.delete();
    }

    onClickEdit(activity) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_id: activity.id,
            res_model: "mail.activity",
            views: [[false, "form"]],
            view_mode: "form",
            target: "new",
            context: {
                default_res_id: activity.res_id,
                default_res_model: activity.res_model,
            },
        });
    }

    openMyActivities() {
        this.action.doAction("mail.mail_activity_action_my", {
            target: this.ui.isSmall ? "new" : "current",
        });
    }
}
