import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { serializeDate } from "@web/core/l10n/dates";

const { DateTime } = luxon;

export const timesheetLeaderboardService = {
    async: ["getLeaderboardData"],
    dependencies: ["orm"],
    start(env, { orm }) {
        let leaderboardData = { leaderboard: [], tip: null };
        if (!browser.localStorage.getItem("leaderboardType")) {
            browser.localStorage.setItem("leaderboardType", "billing_rate");
        }
        let leaderboardType = browser.localStorage.getItem("leaderboardType") || "billing_rate";
        let currentEmployeeId = 0;

        const sortAndFilterLeaderboard = (array) => {
            const min = leaderboardType === "billing_rate" ? 0.5 : 0;
            array.sort((a, b) => b[leaderboardType] - a[leaderboardType]);
            return array.filter((line) => line[leaderboardType] > min);
        };

        const setCurrentEmployeeIndexFromLeaderboard = (array) => {
            const index = array.findIndex((object) => object.id === currentEmployeeId);
            const employeeData = array[index];
            if (index >= 0) {
                employeeData.index = index;
            }
            return employeeData;
        };

        const resetLeaderboard = () => {
            leaderboardData = { leaderboard: [], tip: null };
        };

        return {
            get leaderboardType() {
                return leaderboardType;
            },
            get showLeaderboard() {
                return Boolean(leaderboardData.showLeaderboard);
            },
            get showIndicators() {
                return leaderboardData.billableTimeTarget > 0;
            },
            get data() {
                return leaderboardData;
            },
            async getLeaderboardData(
                { periodStart, periodEnd, fetchTips, kwargs } = { fetchTips: true, kwargs: {} }
            ) {
                const today = DateTime.local().startOf("day");

                const start = periodStart || today.startOf("month");
                const stop = periodEnd || today.endOf("month");
                if (leaderboardData.anchor?.equals(start)) {
                    return;
                }
                const {
                    billable_time_target,
                    total_time_target,
                    leaderboard,
                    employee_id,
                    show_leaderboard,
                    tip
                } = await orm.call(
                    "res.company",
                    "get_timesheet_ranking_data",
                    [serializeDate(start), serializeDate(stop), serializeDate(today), !!fetchTips],
                    kwargs
                );
                if (!leaderboard) {
                    resetLeaderboard();
                    return;
                }
                leaderboardData.billableTimeTarget = billable_time_target || 0;
                leaderboardData.totalTimeTarget = total_time_target;
                leaderboardData.leaderboardRaw = leaderboard;
                leaderboardData.leaderboard = sortAndFilterLeaderboard(leaderboard);
                leaderboardData.showLeaderboard = show_leaderboard;

                if (fetchTips && tip) {
                    leaderboardData.tip = tip;
                }

                currentEmployeeId = employee_id;
                leaderboardData.currentEmployee = setCurrentEmployeeIndexFromLeaderboard(
                    leaderboardData.leaderboard
                );
                leaderboardData.anchor = start;
            },
            changeLeaderboardType(type) {
                leaderboardType = type;
                browser.localStorage.setItem("leaderboardType", type);
                leaderboardData.leaderboard = sortAndFilterLeaderboard(
                    leaderboardData.leaderboardRaw
                );
                leaderboardData.currentEmployee = setCurrentEmployeeIndexFromLeaderboard(
                    leaderboardData.leaderboard
                );
            },
            resetLeaderboard,
        };
    },
};

registry.category("services").add("timesheet_leaderboard", timesheetLeaderboardService);
