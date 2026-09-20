import { expect, test } from "@odoo/hoot";

import { mountView, onRpc } from "@web/../tests/web_test_helpers";

import { defineTimesheetModels } from "./sale_timesheet_models";

defineTimesheetModels();

async function initAndOpenView(showIndicator = true, showLeaderboard = true) {
    onRpc("get_timesheet_ranking_data", (params) => {
        expect(params.model).toBe("res.company");
        expect.step("get_timesheet_ranking_data");
        if (!showIndicator) {
            return {};
        }
        const leaderboardData = {
            leaderboard: [...Array(11).keys()].map((id) => ({
                id: id,
                name: `Test ${id}`,
                billable_time_target: 100.0,
                billable_time: 150.0,
                total_time: 150.0,
                total_valid_time: 150.0,
                billing_rate: 150.0,
            })),
            employee_id: 1,
            billable_time_target: 100.0,
            total_time_target: 144.0,
            show_leaderboard: showLeaderboard,
        };
        if (!showLeaderboard) {
            leaderboardData.leaderboard = [
                leaderboardData.leaderboard.find((d) => d.id === leaderboardData.employee_id),
            ];
        }
        return leaderboardData;
    });
    await mountView({
        resModel: "account.analytic.line",
        type: "list",
        arch: `
            <list js_class="timesheet_timer_list">
                <field name="name"/>
            </list>`,
    });
}

test("Check that leaderboard is displayed if user's company has the features on.", async () => {
    await initAndOpenView();
    expect(".o_timesheet_leaderboard").toHaveCount(1);
    expect.verifySteps(["get_timesheet_ranking_data"]);
});

test("Check that leaderboard is not displayed if user's company doesn't have the features on.", async () => {
    await initAndOpenView(false, false);
    expect(".o_timesheet_leaderboard").toHaveCount(0);
    expect.verifySteps(["get_timesheet_ranking_data"]);
});
