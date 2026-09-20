import { expect, test } from "@odoo/hoot";
import {
    contains,
    mountWithCleanup,
    makeMockEnv,
    defineModels,
} from "@web/../tests/web_test_helpers";
import { mailModels } from "@mail/../tests/mail_test_helpers";

import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";

// Due to dependency with mail module, we have to define their models for our tests.
defineModels(mailModels);

test("can change the date filter by editing textually", async () => {
    const date = {
        filter: "this_month",
        mode: "range",
        period_type: "month",
    };

    const env = await makeMockEnv({
        controller: {
            filters: {
                show_period_comparison: false,
            },
            userGroups: {},
            cachedUserGroups: {},
            incrementCallNumber: (cacheKey) => {},
            cachedFilterOptions: {
                available_horizontal_groups: [],
                available_variants: [],
                companies: [],
                date: date,
                rounding_unit: "decimals",
                rounding_unit_names: {
                    decimals: ".$",
                },
            },
            reload: (optionPath, newOptions) => {
                expect.step(`reload ${optionPath} to ${newOptions}`);
            },
            updateOption: (option, value) => {
                expect.step(`update option ${option} to ${value}`);
                if (option === "date.filter") {
                    date.filter = value;
                    date.period_type = value.split("_")[1];
                }
            },
            revision: 0,
        },
        template: (name) => "account_reports.AccountReportFiltersCustomizable",
        component: (name) => AccountReportFilters,
    });

    const filters = await mountWithCleanup(AccountReportFilters, { env });
    // Default date = 2019-03-11

    // Open Date Filter dropdown
    await contains("#filter_date > button.o-dropdown").click();

    // Click the Month input when selected
    await contains(".date_filter_month.selected .input_current_date").click();
    // Edit the month by changing the text (+14 months)
    await contains(".date_filter_month .input_current_date:not([readonly])").edit("May 2020");
    // Click the Month input when selected
    await contains(".date_filter_month.selected .input_current_date").click();
    // Edit the month by changing the text (-10 months)
    await contains(".date_filter_month .input_current_date:not([readonly])").edit("May 2018");
    // Click the Month input when selected
    await contains(".date_filter_month.selected .input_current_date").click();
    // Edit the month by changing the text to something invalid
    await contains(".date_filter_month .input_current_date:not([readonly])").edit("Invalid Month");

    // Select the Quarter filter
    await contains(".date_filter_quarter").click();
    // Force re-render that's normally done by the controller
    filters.render();

    // Click the Quarter input when selected
    await contains(".date_filter_quarter.selected .input_current_date").click();
    // Edit the quarter by changing the text (+5 quarters)
    await contains(".date_filter_quarter .input_current_date:not([readonly])").edit("Apr - Jun 2020");
    // Click the Quarter input when selected
    await contains(".date_filter_quarter.selected .input_current_date").click();
    // Edit the quarter by changing the text (-3 quarters)
    await contains(".date_filter_quarter .input_current_date:not([readonly])").edit("Apr - Jun 2018");
    // Click the Quarter input when selected
    await contains(".date_filter_quarter.selected .input_current_date").click();
    // Edit the quarter by changing the text (invalid quarter, -4 quarters)
    await contains(".date_filter_quarter .input_current_date:not([readonly])").edit("Random - Feb 2018");
    // Click the Quarter input when selected
    await contains(".date_filter_quarter.selected .input_current_date").click();
    // Edit the quarter by changing the text to something invalid
    await contains(".date_filter_quarter .input_current_date:not([readonly])").edit("Invalid Quarter");

    // Select the Year filter
    await contains(".date_filter_year").click();
    // Force re-render that's normally done by the controller
    filters.render();

    // Click the Year input when selected
    await contains(".date_filter_year.selected .input_current_date").click();
    // Edit the year by changing the text (+2 years)
    await contains(".date_filter_year .input_current_date:not([readonly])").edit("2021");
    // Click the Year input when selected
    await contains(".date_filter_year.selected .input_current_date").click();
    // Edit the year by changing the text (-1 year)
    await contains(".date_filter_year .input_current_date:not([readonly])").edit("2018");
    // Click the Year input when selected
    await contains(".date_filter_year.selected .input_current_date").click();
    // Edit the year by changing the text to something invalid
    await contains(".date_filter_year .input_current_date:not([readonly])").edit("Invalid Year");

    expect.verifySteps([
        // Set the month to +14 months
        "update option date.filter to next_month",
        "update option date.period to 14",

        // Set the month to -10 months
        "update option date.filter to previous_month",
        "update option date.period to -10",

        // Keep the month the same after entering an invalid value

        // Switch to Quarter
        "update option date.filter to this_quarter",
        "update option date.period to 0",

        // Set the quarter to +5 quarters
        "update option date.filter to next_quarter",
        "update option date.period to 5",

        // Set the quarter to -3 quarters
        "update option date.filter to previous_quarter",
        "update option date.period to -3",

        // Set the quarter to -4 quarters
        "update option date.filter to previous_quarter",
        "update option date.period to -4",

        // Keep the quarter the same after entering an invalid value

        // Switch to Year
        "update option date.filter to this_year",
        "update option date.period to 0",

        // Set the year to +2 years
        "update option date.filter to next_year",
        "update option date.period to 2",

        // Set the year to -1 year
        "update option date.filter to previous_year",
        "update option date.period to -1",

        // Keep the year the same after entering an invalid value
    ]);
});
