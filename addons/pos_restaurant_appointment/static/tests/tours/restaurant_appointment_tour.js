import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import { refresh } from "@point_of_sale/../tests/generic_helpers/utils";
import { registry } from "@web/core/registry";
import * as RestaurantAppointment from "@pos_restaurant_appointment/../tests/tours/utils/restaurant_appointment_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as FloorScreen from "@pos_restaurant/../tests/tours/utils/floor_screen_util";
import * as ProductScreenPos from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ProductScreenResto from "@pos_restaurant/../tests/tours/utils/product_screen_util";
import { delay } from "@web/core/utils/concurrency";

const ProductScreen = { ...ProductScreenPos, ...ProductScreenResto };

registry.category("web_tour.tours").add("RestaurantAppointmentTour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),

            // Make sure there is a currently active order.
            FloorScreen.clickTable("4"),
            ProductScreen.clickDisplayedProduct("Coca-Cola", true),

            // Check that the booking gantt view is shown.
            {
                content:
                    "Wait few ms before clicking on Booking to ensure gantt view will be shown",
                isActive: ["auto"],
                trigger: "body",
                async run() {
                    await delay(1000);
                },
            },
            {
                trigger: ".pos-leftheader button:contains('Booking')",
                run: "click",
            },
            RestaurantAppointment.isKanbanViewShown(),
            refresh(),
            RestaurantAppointment.isKanbanViewShown(),
            Chrome.clickMenuButton(),
            Chrome.clickMenuDropdownOption("Reload Data"),
            Chrome.clickBtn("Limited", { expectUnloadPage: true }),
            RestaurantAppointment.isKanbanViewShown(),
            Chrome.clickMenuButton(),
            Chrome.clickMenuDropdownOption("Reload Data"),
            Chrome.clickBtn("Full", { expectUnloadPage: true }),
            RestaurantAppointment.isKanbanViewShown(),
            Chrome.clickPlanButton(),
            RestaurantAppointment.appointmentLabel(5, "Test Lunch"),
            RestaurantAppointment.checkAppointmentLabelNotPresent(4, "Tomorrow Appointment"),

            // Going back to the table, it should still be possible to add items
            FloorScreen.clickTable("4"),
            ProductScreen.clickDisplayedProduct("Coca-Cola", true),
        ].flat(),
});

registry.category("web_tour.tours").add("test_appointment_kanban_view", {
    steps: () =>
        [
            Chrome.startPoS(),
            Chrome.freezeDateTime(1756297136578),
            Dialog.confirm("Open Register"),
            {
                trigger: ".pos-leftheader button:contains('Booking')",
                run: "click",
            },
            {
                trigger: ".pos .o-kanban-button-new",
                run: "click",
            },
            {
                trigger: ".o_form_renderer .oe_title .o_input",
                run: "edit Test Appointment",
            },
            {
                trigger: ".o_form_renderer .o_field_integer .o_input",
                run: "edit 3",
            },
            {
                trigger: ".o_form_renderer .o_field_many2many_selection .o_input",
                run: "click",
            },
            RestaurantAppointment.selectTable("Test Main Floor - Table 4"), // 2 capacity
            {
                trigger: ".o_form_renderer .o_field_many2many_selection .o_input",
                run: "click",
            },
            RestaurantAppointment.selectTable("Test Main Floor - Table 5"), // 2 capacity
            {
                trigger: ".o_form_button_save",
                run: "click",
            },
            RestaurantAppointment.checkAppointment("Test Appointment"),
            {
                content: "Store the current active hour filter label",
                trigger: ".hour-filter span, .hour-filter",
                run: function () {
                    const current = document.querySelector(".hour-filter span")?.innerText || "";
                    window._currentHourFilter = current || "Morning";
                },
            },
            {
                trigger: ".hour-filter",
                run: "click",
            },
            {
                content: "Select a different hour filter than the current one",
                trigger: ".dropdown-menu",
                run: function () {
                    const options = Array.from(
                        document.querySelectorAll(".dropdown-menu .dropdown-item")
                    );
                    const diff = options.find(
                        (o) => !o.innerText.includes(window._currentHourFilter)
                    );
                    diff?.click();
                    window._otherHourFilter = diff?.innerText;
                },
            },
            RestaurantAppointment.checkAppointmentNotVisible("Test Appointment"),
            {
                trigger: ".hour-filter",
                run: "click",
            },
            {
                content: "Re-select the original hour filter",
                trigger: ".dropdown-menu",
                run: function () {
                    const options = Array.from(
                        document.querySelectorAll(".dropdown-menu .dropdown-item")
                    );
                    const orig = options.find((o) =>
                        o.innerText.includes(window._currentHourFilter)
                    );
                    orig?.click();
                },
            },
            RestaurantAppointment.checkAppointment("Test Appointment"),
            {
                trigger: ".o_kanban_record:contains('Test Appointment')",
                run: "click",
            },
            {
                trigger: ".popover-footer button:contains('Edit')",
                run: "click",
            },
            {
                trigger: ".o_form_renderer .o_field_many2many_selection .o_input",
                run: "click",
            },
            RestaurantAppointment.checkTableOption("3p"),
            RestaurantAppointment.selectTable("Search more..."),
            {
                trigger: ".o_list_renderer tbody tr:first-child td:contains('3p')",
            },
        ].flat(),
});

registry.category("web_tour.tours").add("DuplicateFloorCalendarResource", {
    steps: () =>
        [
            // check floors if they contain their corresponding tables
            Chrome.startPoS(),

            FloorScreen.selectedFloorIs("Main Floor"),
            FloorScreen.hasTable("2"),
            FloorScreen.hasTable("4"),
            FloorScreen.hasTable("5"),

            Chrome.clickMenuOption("Edit Plan"),

            //test copy floor
            FloorScreen.clickFloor("Main Floor"),
            FloorScreen.clickEditButton("Clone"),
            FloorScreen.selectedFloorIs("Main Floor (copy)"),
            FloorScreen.hasTable("2"),
            FloorScreen.hasTable("4"),
            FloorScreen.hasTable("5"),
            FloorScreen.clickSaveEditButton(),
            {
                content: `Check copied floor plan tables have an appointment resource`,
                trigger: ".pos", // dummy trigger
                run: function () {
                    const tables = window.posmodel.models["restaurant.floor"]
                        .find((rf) => rf.name == "Main Floor (copy)")
                        .table_ids?.filter((table) => table.active);
                    for (const table of tables) {
                        if (table.appointment_resource_id === undefined) {
                            console.error(
                                `Table "${table.table_number}" has no appointment_resource_id.`
                            );
                        }
                    }
                },
            },
        ].flat(),
});
