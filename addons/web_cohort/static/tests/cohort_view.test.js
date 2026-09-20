import { expect, getFixture, test } from "@odoo/hoot";
import { queryAll, queryAllTexts } from "@odoo/hoot-dom";
import { animationFrame, Deferred } from "@odoo/hoot-mock";
import { markup } from "@odoo/owl";
import { changeScale } from "@web/../tests/views/calendar/calendar_test_helpers";
import {
    contains,
    defineModels,
    fields,
    getService,
    mockService,
    models,
    mountView,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
    removeFacet,
    toggleMenu,
    toggleMenuItem,
    toggleSearchBarMenu,
} from "@web/../tests/web_test_helpers";
import { browser } from "@web/core/browser/browser";
import { download } from "@web/core/network/download";
import { WebClient } from "@web/webclient/webclient";

class Subscription extends models.Model {
    start = fields.Date();
    stop = fields.Date();
    recurring = fields.Integer({
        string: "Recurring Price",
        aggregator: "sum",
    });

    _records = [
        { id: 1, start: "2017-07-12", stop: "2017-08-11", recurring: 10 },
        { id: 2, start: "2017-08-14", recurring: 20 },
        { id: 3, start: "2017-08-21", stop: "2017-08-29", recurring: 10 },
        { id: 4, start: "2017-08-21", recurring: 20 },
        { id: 5, start: "2017-08-23", recurring: 10 },
        { id: 6, start: "2017-08-24", recurring: 22 },
        { id: 7, start: "2017-08-24", stop: "2017-08-29", recurring: 10 },
        { id: 8, start: "2017-08-24", recurring: 22 },
    ];
}

class Lead extends models.Model {
    start = fields.Date();
    stop = fields.Date();
    revenue = fields.Float();

    _records = [
        { id: 1, start: "2017-07-12", stop: "2017-08-11", revenue: 1200.2 },
        { id: 2, start: "2017-08-14", revenue: 500 },
        { id: 3, start: "2017-08-21", stop: "2017-08-29", revenue: 5599.99 },
        { id: 4, start: "2017-08-21", revenue: 13500 },
        { id: 5, start: "2017-08-23", revenue: 6000 },
        { id: 6, start: "2017-08-24", revenue: 1499.99 },
        { id: 7, start: "2017-08-24", stop: "2017-08-29", revenue: 16000 },
        { id: 8, start: "2017-08-24", revenue: 22000 },
    ];
}

class Attendee extends models.Model {
    event_begin_date = fields.Date({ string: "Event Start Date" });
    registration_date = fields.Date({ string: "Registration Date" });

    _records = [
        {
            id: 1,
            event_begin_date: "2018-06-30",
            registration_date: "2018-06-13",
        },
        {
            id: 2,
            event_begin_date: "2018-06-30",
            registration_date: "2018-06-20",
        },
        {
            id: 3,
            event_begin_date: "2018-06-30",
            registration_date: "2018-06-22",
        },
        {
            id: 4,
            event_begin_date: "2018-06-30",
            registration_date: "2018-06-22",
        },
        {
            id: 5,
            event_begin_date: "2018-06-30",
            registration_date: "2018-06-29",
        },
    ];
}

defineModels([Subscription, Lead, Attendee]);

onRpc("has_group", () => true);

test("simple cohort rendering", async () => {
    await mountView({
        type: "cohort",
        resModel: "subscription",
        arch: '<cohort string="Subscription" date_start="start" date_stop="stop" />',
    });

    expect(".o_cohort_view").toHaveClass("o_view_controller");
    expect(".table").toHaveCount(1, { message: "should have a table" });
    expect(".table thead tr:first th:first:contains(Start)").toHaveCount(1, {
        message: 'should contain "Start" in header of first column',
    });
    expect(".table thead tr:first th:nth-child(3):contains(Stop - By Day)").toHaveCount(1, {
        message: 'should contain "Stop - By Day" in title',
    });
    expect(".table thead tr:nth-child(2) th:first:contains(+0)").toHaveCount(1, {
        message: "interval should start with 0",
    });
    expect(".table thead tr:nth-child(2) th:nth-child(16):contains(+15)").toHaveCount(1, {
        message: "interval should end with 15",
    });

    await toggleMenu("Measures");
    expect(".dropdown-menu:not(.d-none)").toHaveCount(1, {
        message: "should have list of measures",
    });

    await contains(".o_view_scale_selector .scale_button_selection").click();
    expect(".o-dropdown--menu span").toHaveCount(5, {
        message: "should have buttons of intervals",
    });
});

test("quarter cohort rendering", async () => {
    await mountView({
        type: "cohort",
        resModel: "subscription",
        arch: '<cohort string="Subscription" date_start="start" date_stop="stop" />',
    });
    await changeScale("quarter");
    expect(".o_cohort_view").toHaveClass("o_view_controller");
    expect(".table").toHaveCount(1, { message: "should have a table" });
    expect(".table thead tr:first th:first:contains(Start)").toHaveCount(1, {
        message: 'should contain "Start" in header of first column',
    });
    expect(".table thead tr:first th:nth-child(3):contains(Stop - By Quarter)").toHaveCount(1, {
        message: 'should contain "Stop - By Quarter" in title',
    });
    expect(".table tbody tr td:first:contains(Q3 2017)").toHaveCount(1, {
        message: 'should contain "Q3 2017" as start',
    });
    expect(".table thead tr:nth-child(2) th:first:contains(+0)").toHaveCount(1, {
        message: "interval should start with 0",
    });
    expect(".table thead tr:nth-child(2) th:nth-child(7):contains(+6)").toHaveCount(1, {
        message: "interval should end with 6",
    });

    await toggleMenu("Measures");
    expect(".dropdown-menu:not(.d-none)").toHaveCount(1, {
        message: "should have list of measures",
    });

    await contains(".o_view_scale_selector .scale_button_selection").click();
    expect(".o-dropdown--menu span").toHaveCount(5, {
        message: "should have buttons of intervals",
    });
});

test("no content helper", async () => {
    Subscription._records = [];

    await mountView({
        type: "cohort",
        resModel: "subscription",
        arch: '<cohort string="Subscription" date_start="start" date_stop="stop" />',
    });

    expect("div.o_view_nocontent").toHaveCount(1);
    // Renderer is still displayed beside the no content helper
    expect(".o_cohort_renderer").toHaveCount(1);
    expect(".o_content button").toHaveCount(3);
});

test("no content helper after update", async () => {
    Subscription._views = {
        cohort: `<cohort string="Subscription" date_start="start" date_stop="stop" measure="recurring"/>`,
        search: `
            <search>
                <filter name="recurring_bigger_25" string="Recurring bigger than 25" domain="[('recurring', '>', 25)]"/>
            </search>
        `,
    };
    await mountView({
        type: "cohort",
        resModel: "subscription",
        config: {
            views: [[false, "search"]],
        },
    });

    expect("div.o_view_nocontent").toHaveCount(0);

    await toggleSearchBarMenu();
    await toggleMenuItem("Recurring bigger than 25");

    expect("div.o_view_nocontent").toHaveCount(1);
});

test("correctly set by default measure and interval", async () => {
    await mountView({
        type: "cohort",
        resModel: "subscription",
        arch: '<cohort string="Subscription" date_start="start" date_stop="stop" />',
    });

    await toggleMenu("Measures");

    expect(".dropdown-menu span.selected:eq(0)").toHaveText("Count", {
        message: "count should be the default for measure field",
    });

    expect(".o_view_scale_selector button:eq(0)").toHaveText("Day", {
        message: "day should by default for interval",
    });

    expect(".table thead th:eq(1)").toHaveText("Count", {
        message: 'should contain "Count" in header of second column',
    });
    expect(".table thead th:eq(2)").toHaveText("Stop - By Day", {
        message: 'should contain "Stop - By Day" in title',
    });
});

test("correctly sort measure items", async () => {
    // It's important to compare capitalized and lowercased words
    // to be sure the sorting is effective with both of them
    Subscription._fields.flop = fields.Integer({
        string: "Abc",
        store: true,
        aggregator: "sum",
    });
    Subscription._fields.add = fields.Integer({
        string: "add",
        store: true,
        aggregator: "sum",
    });
    Subscription._fields.zoo = fields.Integer({
        string: "Zoo",
        store: true,
        aggregator: "sum",
    });

    await mountView({
        type: "cohort",
        resModel: "subscription",
        arch: '<cohort string="Subscription" date_start="start" date_stop="stop"/>',
    });

    await toggleMenu("Measures");

    expect(queryAllTexts(".dropdown-menu span")).toEqual([
        "Abc",
        "add",
        "Recurring Price",
        "Zoo",
        "Count",
    ]);
});

test("correctly set measure and interval after changed", async () => {
    await mountView({
        type: "cohort",
        resModel: "subscription",
        arch: '<cohort string="Subscription" date_start="start" date_stop="stop" measure="recurring" interval="week" />',
    });

    await toggleMenu("Measures");
    expect(".dropdown-menu span.selected").toHaveText("Recurring Price", {
        message: "should recurring for measure",
    });

    await contains(".o_view_scale_selector .dropdown-toggle").click();
    expect(".o-dropdown--menu .active").toHaveText("Week", { message: "should week for interval" });
    expect(".table thead th:eq(1)").toHaveText("Recurring Price", {
        message: 'should contain "Recurring Price" in header of second column',
    });
    expect(".table thead th:eq(2)").toHaveText("Stop - By Week", {
        message: 'should contain "Stop - By Week" in title',
    });

    await toggleMenu("Measures");
    await contains(".o-dropdown--menu span:not(.selected)").click();
    expect(".o-dropdown--menu span.selected").toHaveText("Count", {
        message: "should active count for measure",
    });
    expect(".table thead th:eq(1)").toHaveText("Count", {
        message: 'should contain "Count" in header of second column',
    });

    await changeScale("month");
    expect(".table thead th:eq(2)").toHaveText("Stop - By Month", {
        message: 'should contain "Stop - By Month" in title',
    });
});

test("cohort view without attribute invisible on field", async () => {
    await mountView({
        type: "cohort",
        resModel: "subscription",
        arch: `<cohort string="Subscription" date_start="start" date_stop="stop"/>`,
    });

    await toggleMenu("Measures");
    expect(".dropdown-menu span").toHaveCount(2);
    expect(".dropdown-menu span:eq(0)").toHaveText("Recurring Price");
    expect(".dropdown-menu span:eq(1)").toHaveText("Count");
});

test("cohort view with attribute invisible on field", async () => {
    await mountView({
        type: "cohort",
        resModel: "subscription",
        arch: `
            <cohort string="Subscription" date_start="start" date_stop="stop">
                <field name="recurring" invisible="1"/>
            </cohort>`,
    });

    await toggleMenu("Measures");
    expect(".dropdown-menu span").toHaveCount(1);
    expect(".dropdown-menu span").not.toHaveText("Recurring Price");
});

test("cohort view with aggregator equals to sum should only visible in measures", async () => {
    Subscription._fields.billing = fields.Integer({
        string: "Billing Period Value",
        store: true,
        aggregator: "avg",
    });
    const recordA = {
        id: 9,
        start: "2024-02-08",
        stop: "2024-02-12",
        recurring: 10,
        billing: 100,
    };
    const recordB = {
        id: 10,
        start: "2024-02-08",
        stop: "2024-02-14",
        recurring: 20,
        billing: 200,
    };
    Subscription._records.push(recordA, recordB);
    await mountView({
        type: "cohort",
        resModel: "subscription",
        arch: `
            <cohort string="Subscription" date_start="start" date_stop="stop">
                <field name="recurring"/>
                <field name="billing"/>
            </cohort>`,
    });

    await toggleMenu("Measures");
    expect(queryAllTexts(".dropdown-menu span")).toEqual(["Recurring Price", "Count"]);
});

test("export cohort button should be disabled when no data", async () => {
    expect.assertions(1);

    Subscription._records = [];

    await mountView({
        type: "cohort",
        resModel: "subscription",
        arch: '<cohort string="Subscription" date_start="start" date_stop="stop" />',
    });

    expect("button.o_cohort_download_button").toHaveAttribute("disabled");
});

test("export cohort", async () => {
    expect.assertions(7);

    const downloadDef = new Deferred();
    patchWithCleanup(download, {
        _download: async (options) => {
            const data = JSON.parse(await options.data.data.text());
            expect(options.url).toBe("/web/cohort/export");
            expect(data.interval_string).toBe("Day");
            expect(data.measure_string).toBe("Count");
            expect(data.date_start_string).toBe("Start");
            expect(data.date_stop_string).toBe("Stop");
            expect(data.title).toBe("Subscription");
            downloadDef.resolve();
        },
    });

    await mountView({
        type: "cohort",
        resModel: "subscription",
        arch: '<cohort string="Subscription" date_start="start" date_stop="stop" />',
    });

    expect("button.o_cohort_download_button").not.toHaveAttribute("disabled");

    await contains(".o_cohort_download_button").click();
    await downloadDef;
});

test.tags("desktop");
test("when clicked on cell redirects to the correct list/form view ", async () => {
    Subscription._views = {
        cohort: `
                <cohort string="Subscriptions" date_start="start" date_stop="stop" measure="__count" interval="week" />`,
        "list,my_list_view": `
                <list>
                    <field name="start"/>
                    <field name="stop"/>
                </list>`,
        "form,my_form_view": `
                <form>
                    <field name="start"/>
                    <field name="stop"/>
                </form>`,
        list: `
                <list>
                    <field name="recurring"/>
                    <field name="start"/>
                </list>`,
        form: `
                <form>
                    <field name="recurring"/>
                    <field name="start"/>
                </form>`,
    };

    await mountWithCleanup(WebClient);

    await getService("action").doAction({
        name: "Subscriptions",
        res_model: "subscription",
        type: "ir.actions.act_window",
        views: [
            [false, "cohort"],
            ["my_list_view", "list"],
            ["my_form_view", "form"],
        ],
    });

    // Going to the list view, while clicking Period / Count cell
    await contains("td.o_cohort_value").click();

    expect(".o_list_view th:eq(1)").toHaveText("Start", {
        message: "First field in the list view should be start",
    });
    expect(".o_list_view th:eq(2)").toHaveText("Stop", {
        message: "First field in the list view should be start",
    });
    // Going back to cohort view
    await contains(".o_back_button").click();
    // Going to the list view
    await contains("td div.o_cohort_value").click();
    expect(".o_list_view th:eq(1)").toHaveText("Start", {
        message: "First field in the list view should be start",
    });
    expect(".o_list_view th:eq(2)").toHaveText("Stop", {
        message: "First field in the list view should be start",
    });
    // Going to the form view
    await contains(".o_list_view .o_data_row .o_data_cell").click();

    expect(".o_form_view .o_field_widget:eq(0)").toHaveAttribute("name", "start", {
        message: "First field in the form view should be start",
    });
    expect(".o_form_view .o_field_widget:eq(1)").toHaveAttribute("name", "stop", {
        message: "Second field in the form view should be stop",
    });
});

test("test mode churn", async () => {
    expect.assertions(3);

    onRpc("get_cohort_data", (args) => {
        expect(args.kwargs.mode).toBe("churn", {
            message: "churn mode should be sent via RPC",
        });
    });
    await mountView({
        type: "cohort",
        resModel: "lead",
        arch: '<cohort string="Leads" date_start="start" date_stop="stop" interval="week" mode="churn" />',
    });

    expect("td .o_cohort_value:eq(0)").toHaveText("0%", {
        message: "first col should display 0 percent",
    });
    expect("td .o_cohort_value:eq(4)").toHaveText("100%", {
        message: "col 5 should display 100 percent",
    });
});

test("test backward timeline", async () => {
    expect.assertions(7);

    onRpc("get_cohort_data", (args) => {
        expect(args.kwargs.timeline).toBe("backward", {
            message: "backward timeline should be sent via RPC",
        });
    });
    await mountView({
        type: "cohort",
        resModel: "attendee",
        arch: '<cohort string="Attendees" date_start="event_begin_date" date_stop="registration_date" interval="day" timeline="backward" mode="churn"/>',
    });
    const columnsTh = queryAll(".table thead tr:nth-child(2) th");
    expect(columnsTh[0]).toHaveText("-15", { message: "interval should start with -15" });
    expect(columnsTh[15]).toHaveText("0", { message: "interval should end with 0" });
    const values = queryAll("td .o_cohort_value");
    expect(values[0]).toHaveText("20%", { message: "first col should display 20 percent" });
    expect(values[5]).toHaveText("40%", { message: "col 6 should display 40 percent" });
    expect(values[7]).toHaveText("80%", { message: "col 8 should display 80 percent" });
    expect(values[14]).toHaveText("100%", { message: "col 15 should display 100 percent" });
});

test.tags("desktop");
test("when clicked on cell redirects to the action list/form view passed in context", async () => {
    Subscription._views = {
        cohort: `
                <cohort string="Subscriptions" date_start="start" date_stop="stop" measure="__count" interval="week" />`,
        "list,my_list_view": `
                <list>
                    <field name="start"/>
                    <field name="stop"/>
                </list>`,
        "form,my_form_view": `
                <form>
                    <field name="start"/>
                    <field name="stop"/>
                </form>`,
        list: `
                <list>
                    <field name="recurring"/>
                    <field name="start"/>
                </list>`,
        form: `
                <form>
                    <field name="recurring"/>
                    <field name="start"/>
                </form>`,
    };

    await mountWithCleanup(WebClient);

    await getService("action").doAction({
        name: "Subscriptions",
        res_model: "subscription",
        type: "ir.actions.act_window",
        views: [[false, "cohort"]],
        context: { list_view_id: "my_list_view", form_view_id: "my_form_view" },
    });

    // Going to the list view, while clicking Period / Count cell
    await contains("td.o_cohort_value").click();

    expect(".o_list_view th:eq(1)").toHaveText("Start", {
        message: "First field in the list view should be start",
    });
    expect(".o_list_view th:eq(2)").toHaveText("Stop", {
        message: "First field in the list view should be start",
    });
    // Going back to cohort view
    await contains(".o_back_button").click();
    // Going to the list view
    await contains("td div.o_cohort_value").click();
    expect(".o_list_view th:eq(1)").toHaveText("Start", {
        message: "First field in the list view should be start",
    });
    expect(".o_list_view th:eq(2)").toHaveText("Stop", {
        message: "First field in the list view should be start",
    });
    // Going to the form view
    await contains(".o_list_view .o_data_row .o_data_cell").click();

    expect(".o_form_view .o_field_widget:eq(0)").toHaveAttribute("name", "start", {
        message: "First field in the form view should be start",
    });
    expect(".o_form_view .o_field_widget:eq(1)").toHaveAttribute("name", "stop", {
        message: "Second field in the form view should be stop",
    });
});

test("verify context", async () => {
    expect.assertions(1);

    onRpc("get_cohort_data", (args) => {
        expect(args.kwargs.context).toEqual({
            allowed_company_ids: [1],
            lang: "en",
            tz: "taht",
            uid: 7,
        });
    });
    await mountView({
        type: "cohort",
        resModel: "subscription",
        arch: '<cohort string="Subscription" date_start="start" date_stop="stop" />',
    });
});

test("empty cohort view with action helper", async () => {
    Subscription._views = {
        cohort: `<cohort date_start="start" date_stop="stop"/>`,
        search: `
            <search>
                <filter name="small_than_0" string="Small Than 0" domain="[('id', '&lt;', 0)]"/>
            </search>
        `,
    };
    await mountView({
        type: "cohort",
        resModel: "subscription",
        context: { search_default_small_than_0: true },
        noContentHelp: markup`<p class="abc">click to add a foo</p>`,
        config: {
            views: [[false, "search"]],
        },
    });

    expect(".o_view_nocontent .abc").toHaveCount(1);
    expect("table").toHaveCount(0);

    await removeFacet("Small Than 0");

    expect(".o_view_nocontent .abc").toHaveCount(0);
    expect("table").toHaveCount(1);
});

test("empty cohort view with sample data", async () => {
    Subscription._views = {
        cohort: `<cohort date_start="start" date_stop="stop"/>`,
        search: `
            <search>
                <filter name="small_than_0" string="Small Than 0" domain="[('id', '&lt;', 0)]"/>
            </search>
        `,
    };

    await mountView({
        type: "cohort",
        resModel: "subscription",
        context: { search_default_small_than_0: true },
        noContentHelp: markup`<p class="abc">click to add a foo</p>`,
        config: {
            views: [[false, "search"]],
        },
        useSampleModel: true,
    });

    expect(".o_cohort_view .o_content").toHaveClass("o_view_sample_data");
    expect(".o_view_nocontent .abc").toHaveCount(1);

    await removeFacet("Small Than 0");

    expect(".o_cohort_view .o_content").not.toHaveClass("o_view_sample_data");
    expect(".o_view_nocontent .abc").toHaveCount(0);
    expect("table").toHaveCount(1);
});

test("non empty cohort view with sample data", async () => {
    Subscription._views = {
        cohort: `<cohort date_start="start" date_stop="stop"/>`,
        search: `
            <search>
                <filter name="small_than_0" string="Small Than 0" domain="[('id', '&lt;', 0)]"/>
            </search>
        `,
    };

    await mountView({
        type: "cohort",
        resModel: "subscription",
        noContentHelp: markup`<p class="abc">click to add a foo</p>`,
        config: {
            views: [[false, "search"]],
        },
        useSampleModel: true,
    });

    expect(getFixture()).not.toHaveClass("o_view_sample_data");
    expect(".o_view_nocontent .abc").toHaveCount(0);
    expect("table").toHaveCount(1);

    await toggleSearchBarMenu();
    await toggleMenuItem("Small Than 0");

    expect(getFixture()).not.toHaveClass("o_view_sample_data");
    expect(".o_view_nocontent .abc").toHaveCount(1);
    expect("table").toHaveCount(0);
});

test("concurrent reloads: add a filter, and directly toggle a measure", async () => {
    let def;
    onRpc("get_cohort_data", () => def);
    await mountView({
        type: "cohort",
        resModel: "subscription",
        arch: `<cohort date_start="start" date_stop="stop"/>`,
        searchViewArch: `
                <search>
                    <filter name="my_filter" string="My Filter" domain="[('id', '&lt;', 2)]"/>
                </search>`,
    });

    expect(".o_cohort_row_clickable").toHaveCount(5);
    expect(".table thead th:eq(1)").toHaveText("Count", {
        message: 'active measure should be "Count"',
    });

    // Set a domain (this reload is delayed)
    def = new Deferred();
    await toggleSearchBarMenu();
    await toggleMenuItem("My Filter");

    expect(".o_cohort_row_clickable").toHaveCount(5);

    // Toggle a measure
    await toggleMenu("Measures");
    await toggleMenuItem("Recurring Price");

    expect(".o_cohort_row_clickable").toHaveCount(5);

    def.resolve();
    await animationFrame();

    expect(".o_cohort_row_clickable").toHaveCount(1);
    expect(".table thead th:eq(1)").toHaveText("Recurring Price", {
        message: 'active measure should be "Recurring Price"',
    });
});

test('cohort view with attribute disable_linking="1"', async () => {
    mockService("action", {
        doAction() {
            throw new Error("Should not be called");
        },
    });

    await mountView({
        type: "cohort",
        resModel: "subscription",
        arch: `<cohort date_start="start" date_stop="stop" disable_linking="1"/>`,
    });
    expect(".table").toHaveCount(1, { message: "should have a table" });
    await contains("td.o_cohort_value").click(); // should not trigger a do_action
});

test("field with widget attribute", async () => {
    await mountView({
        type: "cohort",
        resModel: "subscription",
        arch: `
            <cohort date_start="start" date_stop="stop" measure="recurring">
                <field name="recurring" widget="percentage"/>
            </cohort>
        `,
    });
    expect("td.o_cohort_value:eq(1)").toHaveText("1000%", {
        message: "widget 'percentage' should be applied",
    });
});

test("Scale: scale default is fetched from localStorage", async () => {
    let view;
    patchWithCleanup(browser.localStorage, {
        getItem(key) {
            if (String(key).startsWith("scaleOf-viewId")) {
                return "week";
            }
        },
        setItem(key, value) {
            if (key === `scaleOf-viewId-${view?.env.config.viewId}`) {
                expect.step(`scale_${value}`);
            }
        },
    });

    view = await mountView({
        type: "cohort",
        resModel: "subscription",
        arch: `<cohort date_start="start" date_stop="stop"/>`,
    });

    expect(".scale_button_selection").toHaveText("Week");
    await changeScale("year");
    expect(".scale_button_selection").toHaveText("Year");
    expect.verifySteps(["scale_year"]);
});

test("when middle clicked on cell open records in new window ", async () => {
    patchWithCleanup(browser, {
        open: (url) => {
            expect.step(`opened in new window: ${url}`);
        },
    });
    patchWithCleanup(browser.sessionStorage, {
        setItem(key, value) {
            expect.step(`set ${key}-${value}`);
            super.setItem(key, value);
        },
        getItem(key) {
            const res = super.getItem(key);
            expect.step(`get ${key}-${res}`);
            return res;
        },
    });
    Subscription._views = {
        cohort: `
                <cohort string="Subscriptions" date_start="start" date_stop="stop" measure="__count" interval="week" />`,
        "list,my_list_view": `
                <list>
                    <field name="start"/>
                    <field name="stop"/>
                </list>`,
        "form,my_form_view": `
                <form>
                    <field name="start"/>
                    <field name="stop"/>
                </form>`,
    };

    await mountWithCleanup(WebClient);

    await getService("action").doAction({
        id: 22,
        name: "Subscriptions",
        res_model: "subscription",
        type: "ir.actions.act_window",
        views: [
            [false, "cohort"],
            ["my_list_view", "list"],
            ["my_form_view", "form"],
        ],
    });

    await contains("td.o_cohort_value").click({ ctrlKey: true });
    expect.verifySteps([
        "get menu_id-null",
        "get current_lang-null",
        "get current_state-null",
        "get current_action-null",
        'set current_state-{"actionStack":[{"displayName":"Subscriptions","action":22,"view_type":"cohort"}],"action":22}',
        'set current_action-{"id":22,"name":"Subscriptions","res_model":"subscription","type":"ir.actions.act_window","views":[[false,"cohort"],["my_list_view","list"],["my_form_view","form"]]}',
        "set current_lang-en",
        'get current_action-{"id":22,"name":"Subscriptions","res_model":"subscription","type":"ir.actions.act_window","views":[[false,"cohort"],["my_list_view","list"],["my_form_view","form"]]}',
        'get current_state-{"actionStack":[{"displayName":"Subscriptions","action":22,"view_type":"cohort"}],"action":22}',
        'set current_action-{"type":"ir.actions.act_window","name":"Subscriptions","res_model":"subscription","views":[["my_list_view","list"],["my_form_view","form"]],"view_mode":"list","target":"current","context":{"lang":"en","tz":"taht","uid":7,"allowed_company_ids":[1]},"domain":["&",["start",">=","2017-07-10"],["start","<","2017-07-17"]]}',
        'set current_state-{"actionStack":[{"displayName":"Subscriptions","action":22,"view_type":"cohort"},{"displayName":"Subscriptions","model":"subscription","view_type":"list"}],"model":"subscription"}',
        "opened in new window: /odoo/action-22/m-subscription",
        'set current_action-{"id":22,"name":"Subscriptions","res_model":"subscription","type":"ir.actions.act_window","views":[[false,"cohort"],["my_list_view","list"],["my_form_view","form"]]}',
        'set current_state-{"actionStack":[{"displayName":"Subscriptions","action":22,"view_type":"cohort"}],"action":22}',
    ]);
});
