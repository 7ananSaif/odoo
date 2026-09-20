import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { click, drag, queryText } from "@odoo/hoot-dom";
import { animationFrame, disableAnimations, mockDate } from "@odoo/hoot-mock";
import {
    clickEvent,
    resizeEventToTime
} from "@web/../tests/views/calendar/calendar_test_helpers";
import {
    definePlanningModels,
    planningModels,
    PlanningRole,
    ResourceResource,
} from "./planning_mock_models";

import { contains } from "@mail/../tests/mail_test_helpers";
import {
    defineActions,
    getService,
    mockService,
    mountWithCleanup,
    onRpc
} from "@web/../tests/web_test_helpers";
import { WebClient } from "@web/webclient/webclient";

describe.current.tags("desktop");

class PlanningSlot extends planningModels.PlanningSlot {
    _records = [
        {
            id: 1,
            name: "First Record",
            start_datetime: "2019-03-11 08:00:00",
            end_datetime: "2019-03-11 12:00:00",
            resource_id: 1,
            color: 7,
            role_id: 1,
            state: "draft",
            repeat: true,
        },
        {
            id: 2,
            name: "Second Record",
            start_datetime: "2019-03-13 08:00:00",
            end_datetime: "2019-03-13 12:00:00",
            resource_id: 2,
            color: 9,
            role_id: 2,
            state: "published",
        },
    ];
    _views = {
        calendar: `<calendar class="o_planning_calendar_test"
                    event_open_popup="true"
                    date_start="start_datetime"
                    date_stop="end_datetime"
                    color="color"
                    mode="month"
                    multi_create_view="multi_create_form"
                    js_class="planning_calendar">
                        <field name="resource_id"
                                   filters="1"
                                   avatar_field="avatar_128"
                                   widget="many2one_avatar_resource"
                                   write_model="planning.filter.resource"
                                   write_field="resource_id"
                                   filter_field="checked"
                            />
                        <field name="role_id"/>
                        <field name="state"/>
                        <field name="repeat"/>
                        <field name="recurrence_update"/>
                        <field name="end_datetime"/>
                    </calendar>`,
        list: `<list js_class="planning_tree"><field name="resource_id"/></list>`,
        "form,1": `<form>
                    <field name="start_datetime"/>
                    <field name="end_datetime"/>
                </form>`,
        "form,multi_create_form": `
            <form>
                <group>
                     <field name="template_id" options="{'no_quick_create': True}" required="1"/>
                 </group>
            </form>
        `,
    };
}

planningModels.PlanningSlot = PlanningSlot;

definePlanningModels();
defineActions([
    {
        id: 1,
        name: "planning action",
        res_model: "planning.slot",
        views: [
            [false, "calendar"],
            [false, "list"],
        ],
    },
]);

onRpc("has_access", () => true);

beforeEach(() => {
    ResourceResource._records = [
        { id: 1, name: "Chaganlal", resource_type: "user" },
        { id: 2, name: "Maganlal" , resource_type: "user" },
        { id: 3, name: "atlas", resource_type: "material" },
    ];
    PlanningRole._records = [
        { id: 1, name: "JavaScript Developer", color: 1 },
        { id: 2, name: "Functional Consultant", color: 2 },
    ];

    mockDate("2019-03-13 00:00:00", +1);
    disableAnimations();
});

async function createRecordsInBatch() {
    // select the date
    const { drop, moveTo } = await drag(".fc-day[data-date='2019-03-14']");
    await moveTo(".fc-day[data-date='2019-03-15']");
    await animationFrame();
    await drop();
    await animationFrame();

    await click(".o_multi_selection_buttons .btn:contains(Add)");
    await animationFrame();

    // select shift template
    await click("div[name=template_id] input");
    await animationFrame();
    await click(".o-autocomplete--dropdown-item:contains('template')");
    await animationFrame();

    await click(".o_multi_create_popover .popover-footer .btn:contains(Add)");
    await animationFrame();
}

test("planning calendar view: copy previous week", async () => {
    onRpc("action_copy_previous_week", () => {
        expect.step("copy_previous_week()");
        return {};
    });
    onRpc("auto_plan_ids", function () {
        this.env["planning.slot"].write([2], { resource_id: 1 });
        return { open_shift_assigned: [2] };
    });
    onRpc("get_calendar_filters", () => {
        return [
            {"id": 1, "resource_id": false, "checked": true, "resource_type": false},
            {"id": 2, "resource_id": [1, "Chaganlal"], "checked": true, "resource_type": "user"},
            {"id": 3, "resource_id": [2, "Maganlal"], "checked": true, "resource_type": "user"},
        ];
    });
    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);
    mockService("action", {
        async doAction(action) {
            expect(action).toBe("planning.planning_send_action", {
                message: "should open 'Send Planning By Email' form view",
            });
        },
    });

    // switch to 'week' scale
    await click(".scale_button_selection");
    await animationFrame();

    await click(".o_scale_button_week");
    await animationFrame();

    await click(".o_control_panel_main_buttons .o_button_copy_previous_week");
    await animationFrame();
    // verify action_copy_previous_week() invoked
    expect.verifySteps(["copy_previous_week()"]);

    await click(".o_control_panel_main_buttons .o_button_send_all");
    await animationFrame();

    // Switch the view and verify the notification
    expect(".o_notification_body").toHaveCount(1);
    await click(".o_switch_view.o_list");
    await animationFrame();
    await click(".o_switch_view.o_calendar");
    await animationFrame();
    expect(".o_notification_body").toHaveCount(0);

    // Check for auto plan
    await click(".btn.btn-secondary[title='Automatically plan open shifts and sales orders']");
    await animationFrame();

    // Switch the view and verify the notification
    expect(".o_notification_body").toHaveCount(1);
    await click(".o_switch_view.o_list");
    await animationFrame();
    await click(".o_switch_view.o_calendar");
    await animationFrame();
    expect(".o_notification_body").toHaveCount(0);
});

test("Resize or Drag-Drop should open recurrence update wizard", async () => {
    onRpc("get_calendar_filters", () => {
        return [
            {"id": 1, "resource_id": false, "checked": true, "resource_type": false},
            {"id": 2, "resource_id": [1, "Chaganlal"], "checked": true, "resource_type": "user"},
            {"id": 3, "resource_id": [2, "Maganlal"], "checked": true, "resource_type": "user"},
        ];
    });
    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);

    // switch to 'week' scale
    await click(".scale_button_selection");
    await animationFrame();

    await click(".o_scale_button_week");
    await animationFrame();

    // Change the time of the repeat and normal pills
    await resizeEventToTime(1, "2019-03-11 14:30:00");
    await resizeEventToTime(2, "2019-03-13 14:30:00");

    // In recurrence update wizard -> Select "This shift" and confirm
    await click(".modal-content .btn-primary");
    await animationFrame();

    // Open popover of the repeat pill
    await clickEvent(1);
    expect(".o_cw_popover").toHaveCount(1, { message: "should open a popover clicking on event" });
    expect(
        queryText(
            ".o_cw_popover .o_cw_popover_fields_secondary .list-group-item .o_field_datetime"
        ).split(", ")[1]
    ).toBe("2:30 PM", {
        message: "should have correct start date",
    });

    // Open popover of the normal pill
    await clickEvent(2);
    expect(".o_cw_popover").toHaveCount(1, { message: "should open a popover clicking on event" });
    expect(
        queryText(
            ".o_cw_popover .o_cw_popover_fields_secondary .list-group-item .o_field_datetime"
        ).split(", ")[1]
    ).toBe("2:30 PM", {
        message: "should have correct start date",
    });
});

test("should display a popover with an Edit button for users with admin access when open popover", async () => {
    onRpc("has_group", ({ args }) => args[1] === "planning.group_planning_manager");
    onRpc("get_calendar_filters", () => {
        return [
            {"id": 1, "resource_id": false, "checked": true, "resource_type": false},
            {"id": 2, "resource_id": [1, "Chaganlal"], "checked": true, "resource_type": "user"},
            {"id": 3, "resource_id": [2, "Maganlal"], "checked": true, "resource_type": "user"},
        ];
    });
    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);

    // Open popover of the pill
    await clickEvent(1);
    expect(".o_cw_popover").toHaveCount(1, {
        message: "A popover should open when clicking on the event.",
    });
    expect(".o_cw_popover .o_cw_popover_edit").toHaveCount(1, {
        message: "The popover should contain an Edit button in the footer.",
    });
});

test("should not display an Edit button in the popover for users without admin access when open popover", async () => {
    onRpc("has_group", ({ args }) => args[1] !== "planning.group_planning_manager");
    onRpc("get_calendar_filters", () => {
        return [
            {"id": 1, "resource_id": false, "checked": true, "resource_type": false},
            {"id": 2, "resource_id": [1, "Chaganlal"], "checked": true, "resource_type": "user"},
            {"id": 3, "resource_id": [2, "Maganlal"], "checked": true, "resource_type": "user"},
        ];
    });
    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);

    // Open popover of the pill
    await clickEvent(1);
    expect(".o_cw_popover").toHaveCount(1, {
        message: "A popover should open when clicking on the event.",
    });
    expect(".o_cw_popover .o_cw_popover_edit").toHaveCount(0, {
        message: "The popover should not contain an Edit button in the footer.",
    });
});

test("Display modal to choose recurrence type when deleting recurrent task", async () => {
    onRpc("get_calendar_filters", () => {
        return [
            {"id": 1, "resource_id": false, "checked": true, "resource_type": false},
            {"id": 2, "resource_id": [1, "Chaganlal"], "checked": true, "resource_type": "user"},
            {"id": 3, "resource_id": [2, "Maganlal"], "checked": true, "resource_type": "user"},
        ];
    });
    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);

    await click(".fc-event-main");
    await contains(".o_cw_popover_delete");

    await click(".o_cw_popover_delete");
    await contains("h4.modal-title");

    expect("h4.modal-title").toHaveText("Delete Recurring Shift");
});

test("Display confirm delete modal when deleting non recurrent task", async () => {
    onRpc("get_calendar_filters", () => {
        return [
            {"id": 1, "resource_id": false, "checked": true, "resource_type": false},
            {"id": 2, "resource_id": [1, "Chaganlal"], "checked": true, "resource_type": "user"},
            {"id": 3, "resource_id": [2, "Maganlal"], "checked": true, "resource_type": "user"},
        ];
    });
    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);

    await click(".fc-event-main:eq(1)");
    await contains(".o_cw_popover_delete");

    await click(".o_cw_popover_delete");
    await contains("h4.modal-title");

    expect("h4.modal-title").toHaveText("Bye-bye, record!");
});

/*
* This test ensures that :
* - the 'open shifts' filter is the first one displayed in the filter list
* - the 'open shifts' filter cannot be deleted
* - the 'open shifts' filter is checked by default, even if its 'checked' stored value is false
* - the other filters status depends on the 'checked' stored valued
* - the input date picker is not present
* - the material resources have a wrench icon displayed instead of their avatar icon
*/
test("check filters set up, scale display & cosmetic changes", async () => {

    onRpc("get_calendar_filters", () => {
        return [
            {"id": 1, "resource_id": false, "checked": false, "resource_type": false},
            {"id": 2, "resource_id": [1, "Kalandra"], "checked": false, "resource_type": "user"},
            {"id": 3, "resource_id": [2, "Zana"], "checked": true, "resource_type": "user"},
        ];
    });
    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);

    // 'open shifts' filter is the first in the list
    await expect(".o_calendar_filter_items .o_calendar_filter_item:nth-child(1):contains('Open Shifts')").toHaveCount(1);
    await expect(".o_calendar_filter_items .o_calendar_filter_item").toHaveCount(3);

    // 'open shifts' cannot be deleted
    await expect(".o_calendar_filter_items .o_calendar_filter_item:nth-child(1) .o_remove").toHaveCount(0);
    await expect(".o_remove").toHaveCount(2);

    // 'open shift' filter is forced to true
    await expect(".o_calendar_filter_item:contains('Open Shifts') input").toBeChecked();
    // regular filter depends on the store value
    await expect(".o_calendar_filter_item:contains('Kalandra') input").not.toBeChecked();
    await expect(".o_calendar_filter_item:contains('Zana') input").toBeChecked();

    await click(".o_calendar_filter .o-autocomplete--input");
    await animationFrame();

    // the material resource has a wrench icon displayed instead of the avatar icon
    await expect(".o_calendar_filter li.o-autocomplete--dropdown-item:contains('atlas') .fa-wrench").toHaveCount(1);
    await expect(".o_calendar_filter li.o-autocomplete--dropdown-item:contains('Maganlal') .fa-wrench").toHaveCount(0);

    // switch to 'week' scale
    await click(".scale_button_selection");
    await animationFrame();

    await click(".o_scale_button_week");
    await animationFrame();

    // the calendar is displayed in 'week' scale
    await expect(".o_datetime_picker").toHaveCount(1);
});

test("check creation of records with only the 'open shifts' filter", async () => {

    onRpc("get_calendar_filters", () => {
        return [
            {"id": 1, "resource_id": false, "checked": true, "resource_type": false},
        ];
    });
    let expected_records = [{
        "start_datetime": "2019-03-14 08:00:00",
        "end_datetime": "2019-03-15 16:00:00",
        "template_id": 1,
        "resource_id": false,
    }, {
        "start_datetime": "2019-03-15 08:00:00",
        "end_datetime": "2019-03-16 16:00:00",
        "template_id": 1,
        "resource_id": false,
    }];
    onRpc("create_batch_from_calendar", ({ args: [[], records] }) => {
        if (JSON.stringify(records) === JSON.stringify(expected_records)){
            expect.step("matching record");
        }
        return [];
    });
    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);

    await createRecordsInBatch();

    expect.verifySteps(["matching record"]);
});

test("check creation of records with multiple filters selected", async () => {

    onRpc("get_calendar_filters", () => {
        return [
            {"id": 1, "resource_id": false, "checked": true, "resource_type": false},
            {"id": 2, "resource_id": [1, "Kalandra"], "checked": false, "resource_type": "user"},
            {"id": 3, "resource_id": [2, "Zana"], "checked": true, "resource_type": "user"},
        ];
    });
    let expected_records = [{
        "start_datetime": "2019-03-14 08:00:00",
        "end_datetime": "2019-03-15 16:00:00",
        "template_id": 1,
        "resource_id": false,
    }, {
        "start_datetime": "2019-03-14 08:00:00",
        "end_datetime": "2019-03-15 16:00:00",
        "template_id": 1,
        "resource_id": 2,
    }, {
        "start_datetime": "2019-03-15 08:00:00",
        "end_datetime": "2019-03-16 16:00:00",
        "template_id": 1,
        "resource_id": false,
    }, {
        "start_datetime": "2019-03-15 08:00:00",
        "end_datetime": "2019-03-16 16:00:00",
        "template_id": 1,
        "resource_id": 2,
    }]
    onRpc("create_batch_from_calendar", ({ args: [[], records] }) => {
        if (JSON.stringify(records) === JSON.stringify(expected_records)){
            expect.step("matching record");
        }
        return [];
    });
    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);

    await createRecordsInBatch();

    expect.verifySteps(["matching record"]);
});

test("check creation of records while no filter is selected", async () => {
    onRpc("get_calendar_filters", () => {
        return [
            {"id": 1, "resource_id": false, "checked": false, "resource_type": false},
        ];
    });
    onRpc("write", () => {
        // there's no need to update the data set. The 'checked' value is already set to false in the
        // get_calendar_filters and since the view was already loaded, the value will not get overwritten to true.
        return [];
    });
    onRpc("create_batch_from_calendar", ({ args: [[], records] }) => {
        expect.step("create_batch_from_calendar");
    });

    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);

    await click(".o_calendar_filter_item input");
    await animationFrame();

    await createRecordsInBatch();

    expect.verifySteps([]);
});

test("planning calendar view: print", async () => {
    onRpc("get_calendar_filters", () => {
        return [
            {"id": 1, "resource_id": false, "checked": false, "resource_type": false},
        ];
    });
    onRpc("action_print_plannings", () => {
        expect.step("action_print_plannings()");
        return false;
    });
    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);

    await animationFrame();
    await click(".o_button_print");
    expect.verifySteps(["action_print_plannings()"]);
});
