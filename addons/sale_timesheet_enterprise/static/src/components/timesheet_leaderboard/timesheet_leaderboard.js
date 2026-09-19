import { Many2OneAvatarRankField } from "@sale_timesheet_enterprise/components/many2one_avatar_rank_field/many2one_avatar_rank_field";
import { Component } from "@odoo/owl";
import { TimesheetLeaderboardDialog } from "@sale_timesheet_enterprise/views/timesheet_leaderboard_dialog/timesheet_leaderboard_dialog";

import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const { DateTime } = luxon;

export class TimesheetLeaderboard extends Component {
    static template = "sale_timesheet_enterprise.TimesheetLeaderboard";
    static components = {
        Many2OneAvatarRankField,
    };
    static props = {
        model: { type: Object, optional: true },
        date: { type: Object, optional: true },
    };
    static defaultProps = {
        date: DateTime.local().startOf("month"),
    };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.timesheetLeaderboardService = useService("timesheet_leaderboard");
        this.timesheetUOMService = useService("timesheet_uom");
    }

    openLeaderboardPopup() {
        this.dialog.add(TimesheetLeaderboardDialog, {
            date: this.props.date,
            model: this.props.model,
        });
    }

    get isMobile() {
        return this.env.isSmall;
    }

    get avatarDisplayLimit() {
        return (this.timesheetLeaderboardService.data.currentEmployee?.index || 0) < 3 - this.isMobile ? 3 - this.isMobile : 2 - this.isMobile;
    }

    get currentBillingRateText() {
        const percentage = Math.round(this.timesheetLeaderboardService.data.currentEmployee.billing_rate);
        return this.isMobile ? _t("%(percentage)s%", {percentage}) : _t("(%(percentage)s%)", {percentage});
    }

    get currentBillableTimeText() {
        return this.format(this.timesheetLeaderboardService.data.currentEmployee.billable_time);
    }

    get currentBillingText() {
        return _t("%(currentBillableTimeText)s / %(currentTargetTotalTimeText)s ", {
            currentBillableTimeText: this.currentBillableTimeText,
            currentTargetTotalTimeText: this.currentTargetTotalTimeText,
        });
    }

    get currentTotalTimeText() {
       return this.timesheetUOMService.formatter(this.timesheetLeaderboardService.data.currentEmployee.total_time);
    }

    get currentTargetTotalTimeText() {
        return this.format(this.timesheetLeaderboardService.data.currentEmployee.billable_time_target);
    }

    format(value) {
        return this.timesheetUOMService.formatter(value, {
            noLeadingZeroHour: true,
        }).replace(/(:00|\.00)/g, "");
    }
}
