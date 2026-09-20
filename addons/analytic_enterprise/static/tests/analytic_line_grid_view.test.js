import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { queryAllTexts } from "@odoo/hoot-dom";
import { mockDate } from "@odoo/hoot-mock";

import { defineMailModels } from "@mail/../tests/mail_test_helpers";

import { defineModels, fields, models, mountView, onRpc } from "@web/../tests/web_test_helpers";

class AccountAnalyticLine extends models.Model {
    _name = "account.analytic.line";

    account_id = fields.Many2one({ string: "Analytic Account", relation: "account.analytic" });
    date = fields.Date({ string: "Date" });
    unit_amount = fields.Float({ string: "Unit Amount", aggregator: "sum" });

    _records = [
        {
            id: 1,
            account_id: 31,
            date: "2017-01-24",
            unit_amount: 2.5,
        },
        {
            id: 2,
            account_id: 31,
            date: "2017-01-25",
            unit_amount: 2,
        },
        {
            id: 3,
            account_id: 31,
            date: "2017-01-25",
            unit_amount: 5.5,
        },
        {
            id: 4,
            account_id: 31,
            date: "2017-01-30",
            unit_amount: 10,
        },
        {
            id: 5,
            account_id: 142,
            date: "2017-01-31",
            unit_amount: -3.5,
        },
    ];

    _views = {
        grid: `
            <grid js_class="analytic_line_grid">
                <field name="account_id" type="row"/>
                <field name="date" type="col">
                    <range name="year" string="Year" span="year" step="month"/>
                    <range name="month" string="Month" span="month" step="day"/>
                </field>
                <field name="unit_amount" type="measure" widget="float_time"/>
            </grid>
        `,
    };
}

class AccountAnalytic extends models.Model {
    _name = "account.analytic";

    display_name = fields.Char({ string: "Analytic Account Name" });

    _records = [
        { id: 31, display_name: "P1" },
        { id: 142, display_name: "Webocalypse Now" },
    ];
}

defineModels([AccountAnalyticLine, AccountAnalytic]);
defineMailModels();

beforeEach(() => {
    mockDate("2017-01-30 00:00:00");
});

onRpc("account.analytic.line", "grid_unavailability", () => ({}));

onRpc("account.analytic.line", "grid_compute_year_range", () => ({
    date_from: "2016-05-01",
    date_to: "2017-04-30",
}));

describe("AnalyticLineGrid", () => {
    test("display right period on grid view in year range", async () => {
        await mountView({
            type: "grid",
            resModel: "account.analytic.line",
        });
        const columnsText = queryAllTexts(
            ".o_grid_column_title:not(.o_grid_row_total,.o_grid_navigation_wrap)"
        );
        expect(columnsText.length).toEqual(12, {
            message: "12 columns should be rendered to display 12 months",
        });
        expect(columnsText[0]).toEqual("May\n2016");
        expect(columnsText[11]).toEqual("April\n2017");
    });
});
