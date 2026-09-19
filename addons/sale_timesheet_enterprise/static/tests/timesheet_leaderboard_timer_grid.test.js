import { expect, test, beforeEach, describe } from "@odoo/hoot";
import { queryAllTexts, queryAll, queryOne } from "@odoo/hoot-dom";
import { mockDate, animationFrame } from "@odoo/hoot-mock";

import { mountView, contains, onRpc } from "@web/../tests/web_test_helpers";

import { patchSession } from "@hr_timesheet/../tests/hr_timesheet_models";
import { defineTimesheetModels } from "./sale_timesheet_models";

let rankingData;

defineTimesheetModels();

async function initAndOpenView(showIndicator = true, showLeaderboard = true) {
    onRpc("get_timesheet_ranking_data", ({ args }) => {
        if (!showIndicator) {
            return {};
        }
        const leaderboardData = rankingData[args[0]];
        leaderboardData.show_leaderboard = showLeaderboard;
        if (!showLeaderboard) {
            leaderboardData.leaderboard = [
                leaderboardData.leaderboard.find((d) => d.id === leaderboardData.employee_id),
            ];
        }
        return leaderboardData;
    });
    onRpc("read", ({ args }) => {
        if (
            args[1].length === 2 &&
            args[1][0] === "timesheet_show_rates" &&
            args[1][1] === "timesheet_show_leaderboard"
        ) {
            return [
                {
                    timesheet_show_rates: showIndicator,
                    timesheet_show_leaderboard: showLeaderboard,
                },
            ];
        }
    });
    await mountView({
        resModel: "account.analytic.line",
        type: "grid",
        groupBy: ["employee_id", "task_id"],
        arch: `<grid js_class="timer_timesheet_grid">
                    <field name="date" type="col">
                        <range name="week" string="Week" span="week" step="day"/>
                        <range name="month" string="Month" span="month" step="day"/>
                    </field>
                    <field name="unit_amount" type="measure" widget="timesheet_uom"/>
                </grid>`,
    });
}

describe.current.tags("desktop");

beforeEach(() => {
    patchSession();
    mockDate("2017-04-25 00:00:00", +1);
    rankingData = {
        "2017-02-01": {
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
            tip: "February motivation tip!",
        },
        "2017-03-01": {
            leaderboard: [
                {
                    id: 6,
                    name: "User 5",
                    billable_time_target: 100.0,
                    billable_time: 148.0,
                    total_time: 148.0,
                    total_valid_time: 148.0,
                    billing_rate: 148.0,
                },
            ],
            billable_time_target: 100.0,
            employee_id: 1,
            total_time_target: 144.0,
            tip: "March productivity tip!",
        },
        "2017-04-01": {
            leaderboard: [
                {
                    id: 1,
                    name: "Administrator",
                    billable_time_target: 100.0,
                    billable_time: 20.0,
                    total_time: 20.0,
                    total_valid_time: 20.0,
                    billing_rate: 100.0,
                },
                {
                    id: 2,
                    name: "User 1",
                    billable_time_target: 50.0,
                    billable_time: 40.0,
                    total_time: 40.0,
                    total_valid_time: 40.0,
                    billing_rate: 80.0,
                },
                {
                    id: 3,
                    name: "User 2",
                    billable_time_target: 100.0,
                    billable_time: 60.0,
                    total_time: 60.0,
                    total_valid_time: 60.0,
                    billing_rate: 60.0,
                },
                {
                    id: 4,
                    name: "User 3",
                    billable_time_target: 200.0,
                    billable_time: 80.0,
                    total_time: 80.0,
                    total_valid_time: 80.0,
                    billing_rate: 40.0,
                },
                {
                    id: 5,
                    name: "User 4",
                    billable_time_target: 500.0,
                    billable_time: 100.0,
                    total_time: 100.0,
                    total_valid_time: 100.0,
                    billing_rate: 20.0,
                },
            ],
            employee_id: 1,
            billable_time_target: 100.0,
            total_time_target: 144.0,
            tip: "Great work this month!",
        },
        "2017-05-01": {
            leaderboard: [
                {
                    id: 7,
                    name: "User 6",
                    billable_time_target: 100.0,
                    billable_time: 128.0,
                    total_time: 128.0,
                    total_valid_time: 128.0,
                    billing_rate: 128.0,
                },
            ],
            employee_id: 1,
            billable_time_target: 100.0,
            total_time_target: 120.0,
            tip: "May excellence tip!",
        },
    };
});

test("Check that leaderboard is displayed if user's company has the feature on.", async () => {
    await initAndOpenView();
    expect(".o_timesheet_leaderboard").toHaveCount(1);
    expect(".o_timesheet_leaderboard_confetti").toHaveCount(1);
    expect(".o_timesheet_leaderboard span:nth-of-type(3)").toHaveClass("text-success");
    expect(".o_timesheet_leaderboard span:nth-of-type(5)").toHaveClass("text-danger");
    expect(".o_timesheet_leaderboard span:contains('...')").toHaveCount(0);
});

test("Check that leaderboard is not displayed if user's company doesn't have the features on.", async () => {
    await initAndOpenView(false, false);
    expect(".o_timesheet_leaderboard").toHaveCount(0);
});

test("Check that billing and total time indicators are displayed if user's company has the feature on.", async () => {
    await initAndOpenView(true, false);
    expect(".o_timesheet_leaderboard span:contains('Billing: ')").toHaveCount(1);
    expect(".o_timesheet_leaderboard span span:contains('Timesheets')").toHaveCount(1);
});

test("Check that confetties are not displayed if current employee is not first in the leaderboard", async () => {
    const rankingDataApril = rankingData["2017-04-01"];
    const employee = rankingDataApril["leaderboard"][0];
    employee["billing_rate"] = 20.0;
    await initAndOpenView();
    expect(".o_timesheet_leaderboard_confetti").toHaveCount(0);
    await contains(".o_view_scale_selector > button").click();
    await contains(".o_scale_button_month").click();
    await contains("span[aria-label='Previous']").click();
    expect(".o_timesheet_leaderboard_confetti").toHaveCount(0);
});

test("Check that the billing rate is displayed in red if < than 100.", async () => {
    const rankingDataApril = rankingData["2017-04-01"];
    const employee = rankingDataApril["leaderboard"][0];
    employee["billing_rate"] = 70.0;
    await initAndOpenView();
    expect(".o_timesheet_leaderboard span:nth-of-type(3)").toHaveClass("text-danger");
});

test("Check that the total time is displayed without styling if the total valid time >= total time target.", async () => {
    const rankingDataApril = rankingData["2017-04-01"];
    const employee = rankingDataApril["leaderboard"][0];
    employee["total_valid_time"] = 145.0;
    await initAndOpenView();
    expect(".o_timesheet_leaderboard span:nth-of-type(5).text-danger").toHaveCount(0);
});

test("Check that the indicators are replaced by text if current employee's billing rate <= 0 [Leaderboard feature only].", async () => {
    const rankingDataApril = rankingData["2017-04-01"];
    const employee = rankingDataApril["leaderboard"][0];
    employee["billing_rate"] = 0.0;
    await initAndOpenView();
    expect(".o_timesheet_leaderboard span").toHaveText("Record timesheets to earn your rank!");
});

test("Check that the indicators are replaced by text if current employee's billing rate <= 0 [Billing Rate feature only].", async () => {
    const rankingDataApril = rankingData["2017-04-01"];
    const employee = rankingDataApril["leaderboard"][0];
    employee["billing_rate"] = 0.0;
    await initAndOpenView(true, false);
    expect(".o_timesheet_leaderboard span").toHaveText(
        "Record timesheets to determine your billing rate!"
    );
});

test("Check that '···' is displayed when current emplyee's ranking > 3", async () => {
    const rankingDataApril = rankingData["2017-04-01"];
    const employee = rankingDataApril["leaderboard"][0];
    employee["billing_rate"] = 5.0;
    await initAndOpenView();
    expect(".o_timesheet_leaderboard span:contains('···')").toHaveCount(1);
});

test("Check that employees are sorted accordingly to the ranking criteria.", async () => {
    await initAndOpenView();
    await contains(".o_timesheet_leaderboard div[role='button']").click();
    await animationFrame();
    await contains(".modal-content .dropdown-toggle").click();
    await contains(".modal-content .dropdown-menu :eq(1)").click();
    await animationFrame();
    expect(localStorage.getItem("leaderboardType")).toEqual("total_time");
    expect(queryAllTexts(".modal-content .o_employee_name")).toEqual([
        "User 4",
        "User 3",
        "User 2",
        "User 1",
        "Administrator",
    ]);
    await contains(".modal-content .dropdown-toggle").click();
    await contains(".modal-content .dropdown-menu :eq(0)").click();
    await animationFrame();
    expect(localStorage.getItem("leaderboardType")).toEqual("billing_rate");
    expect(queryAllTexts(".modal-content .o_employee_name")).toEqual([
        "Administrator",
        "User 1",
        "User 2",
        "User 3",
        "User 4",
    ]);
});

test("Check that employee's name is displayed in bold if rank > 3.", async () => {
    const rankingDataApril = rankingData["2017-04-01"];
    const employee = rankingDataApril["leaderboard"][0];
    employee["billing_rate"] = 5.0;
    await initAndOpenView();
    await contains(".o_timesheet_leaderboard div[role='button']").click();
    await animationFrame();
    expect(queryAll(".o_employee_name").pop().parentNode).toHaveClass("fw-bolder");
});

test("Check that the month changing buttons work.", async () => {
    await initAndOpenView();
    await contains(".o_timesheet_leaderboard div[role='button']").click();
    await contains(queryOne(".modal-content .oi-chevron-left").parentNode).click();
    expect("span:contains('User 5')").toHaveCount(1);
    expect("span:contains('March 2017')").toHaveCount(1);
    await contains(queryOne(".modal-content .oi-chevron-right").parentNode).click();
    expect("span:contains('Administrator')").toHaveCount(1);
    expect("span:contains('April 2017')").toHaveCount(1);
    await contains(queryOne(".modal-content .oi-chevron-right").parentNode).click();
    expect("span:contains('User 6')").toHaveCount(1);
    expect("span:contains('May 2017')").toHaveCount(1);
    await contains(queryOne(".modal-content .oi-chevron-left").parentNode.nextSibling).click();
    expect("span:contains('Administrator')").toHaveCount(1);
    expect("span:contains('April 2017')").toHaveCount(1);
});

test("Check that the 'Show more' and 'Show less' buttons works.", async () => {
    await initAndOpenView();
    await contains(".o_timesheet_leaderboard div[role='button']").click();
    await contains(queryOne(".modal-content .modal-body .oi-chevron-left").parentNode).click();
    await contains(queryOne(".modal-content .modal-body .oi-chevron-left").parentNode).click();
    expect(".modal-body td:contains('Test 10')").toHaveCount(0);
    await contains(".o_leaderboard_modal_table ~ span").click();
    expect(".modal-body td:contains('Test 10')").toHaveCount(1);
    await contains(".o_leaderboard_modal_table ~ span").click();
    expect(".modal-body td:contains('Test 10')").toHaveCount(0);
});
test("Check that tip is visible when leaderboard dialog is opened", async () => {
    await initAndOpenView();
    await contains(".o_timesheet_leaderboard div[role='button']").click();
    await animationFrame();
    expect(".modal-content").toHaveCount(1);
    expect(".modal-content:contains('April 2017')").toHaveCount(1);
    expect(".modal-content .o_timesheet_leaderboard_tip").toHaveCount(1);
    await contains(queryOne(".modal-content .oi-chevron-left").parentNode).click();
    expect(".modal-content:contains('March 2017')").toHaveCount(1);
    expect(".modal-content .o_timesheet_leaderboard_tip").toHaveCount(1);
    await contains(queryOne(".modal-content .oi-chevron-right").parentNode).click();
    await contains(queryOne(".modal-content .oi-chevron-right").parentNode).click();
    expect(".modal-content:contains('May 2017')").toHaveCount(1);
    expect(".modal-content .o_timesheet_leaderboard_tip").toHaveCount(1);
});
