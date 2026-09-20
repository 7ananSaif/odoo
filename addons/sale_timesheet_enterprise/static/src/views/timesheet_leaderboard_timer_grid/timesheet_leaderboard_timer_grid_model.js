import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import { TimerTimesheetGridModel } from "@timesheet_grid/views/timer_timesheet_grid/timer_timesheet_grid_model";

// this patch is needed because the load() method empties out the past data and prevents keeping persistent data
patch(TimerTimesheetGridModel, {
    services: [...TimerTimesheetGridModel.services, "timesheet_leaderboard"],
});
patch(TimerTimesheetGridModel.prototype, {
    setup(params, services) {
        super.setup(params, services);
        this.timesheetLeaderboardService = services.timesheet_leaderboard;
    },

    async load() {
        const leaderboardData = this.timesheetLeaderboardService.data;
        const promises = [];

        if (!leaderboardData.anchor?.equals(this.navigationInfo.periodStart.startOf("month"))) {
            promises.push(this._getLeaderboardData());
        }
        promises.push(super.load(...arguments));
        return await Promise.all(promises);
    },

    async _getLeaderboardData() {
        const periodStart = this.navigationInfo.periodStart.startOf("month");
        const periodEnd = periodStart.endOf("month");

        if (this.orm.isSample) {
            this.timesheetLeaderboardService.resetLeaderboard();
        } else {
            this.timesheetLeaderboardService.getLeaderboardData({
                periodStart,
                periodEnd,
                fetchTips: true,
                kwargs: { context: user.context },
            });
        }
    },
});
