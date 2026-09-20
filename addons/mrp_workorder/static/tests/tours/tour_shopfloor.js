import { registry } from "@web/core/registry";
import { assert } from "@stock/../tests/tours/tour_helper";
import { stepUtils } from "./tour_step_utils";
import * as helper from "./running_tour_action_helper";

registry.category("web_tour.tours").add("test_shop_floor", {
    steps: () => [
        // SHOP FLOOR CONFIGURATION
        // Select the workcenter the first time we enter in shopfloor.
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Jungle"),
        ...stepUtils.addWorkcenterToDisplay("Savannah"),
        ...stepUtils.confirmWorkcentersSelection(),
        {
            trigger: '.o_work_centers_container button.o_work_center_btn:contains("Jungle")',
            run() {
                helper.assertSearchFacets([{ value: "MO Ready" }]);
            },
        },
        // Select two employees: one by scanning her badge ID and one by clicking on him.
        ...stepUtils.openEmployeesList(),
        {
            content: "Scan Abbie Seedy's badge",
            trigger: ".modal-body .o_mrp_operatos_dialog",
            run: "scan 659898105101",
        },
        { trigger: ".o_mrp_operatos_dialog li[name='Abbie Seedy'].active" },
        ...stepUtils.addEmployee("Billy Demo"),
        // Confirm the employees' selection.
        { trigger: ".modal-footer button.btn-primary", run: "click" },
        { trigger: ".o_mrp_employees_panel li:contains(Billy Demo)", run: "click" },
        { trigger: ".o_mrp_employees_panel li:contains(Abbie Seedy):not(.o_admin_user)" },
        { trigger: ".o_mrp_employees_panel li:contains(Billy Demo).o_admin_user" },
        {
            content: "Go to workcenter Savannah from MO card",
            trigger: '.o_mrp_record_line .o_tag:contains("Savannah")',
            run: "click",
        },

        // PROCESS FIRST WORKORDER
        {
            trigger: '.o_work_centers_container button.active:contains("Savannah")',
            run() {
                helper.assertWorkOrderValues({
                    name: "TWH/MO/00001",
                    operation: "Creation",
                    product: "Giraffe",
                    quantity: "2 Units",
                    steps: [
                        { label: "Register Production" },
                        { label: "Instructions" },
                        { label: "Register legs", value: "8 Units" },
                        { label: "Register necks", value: "2 Units" },
                        { label: "TWH/Stock / NE1", value: "1 Units" },
                        { label: "TWH/Stock / NE2", value: "1 Units" },
                        { label: "Release" },
                    ],
                });
            },
        },
        {
            content: "Start the workorder on header click",
            trigger: 'span.o_finished_product:contains("Giraffe")',
            run: "click",
        },
        {
            content: "Register production check",
            trigger: ".o_mrp_record_line:contains('Register Production') .btn-outline-secondary",
            run: "click",
        },
        // Handle mrp.production.serials wizard
        {
            content: "Register production: Giraffe",
            trigger: ".o_workorder_bar_content:contains('Generate Lot') .btn-primary",
            run: "click",
        },
        {
            trigger: ".btn-primary:contains('Validate')",
            run: "click",
        },
        // Produced product's lot should be displayed and "Register Production" should be crossed.
        { trigger: ".text-decoration-line-through:contains('Register Production')" },
        { trigger: ".o_line_value:contains('0000001')" },

        // Check the instruction then mark it as read.
        { trigger: ".o_mrp_record_line:nth-child(2) .fa-info", run: "click" },
        {
            trigger: ".o_tablet_popups.o_worksheet_modal .o_tablet_instruction_note",
            run() {
                assert(this.anchor.innerText, "Create this giraffe with a lot of care !");
            },
        },
        {
            content: "Close the instruction popup",
            trigger: ".o_tablet_popups.o_worksheet_modal .modal-header .btn-close",
            run: "click",
        },
        {
            content: "Mark the instruction as read",
            trigger: ".o_web_client:not(.modal-open) .o_mrp_record_line:nth-child(2) .fa-check",
            run: "click",
        },
        {
            content: "Register legs consumption by scanning product's barcode",
            trigger: ".o_mrp_record_line:nth-child(2) .fa-undo",
            run: "scan PRODUCT_LEG",
        },
        { trigger: ".modal-content input.o_input:value(8)" },
        { trigger: ".modal-content footer.modal-footer button.btn-primary", run: "click" },
        { trigger: ".o_mrp_record_line:nth-child(3) .o_line_label.text-decoration-line-through" },
        {
            content: "Undo previous marked quantity",
            trigger: ".o_mrp_record_line:nth-child(3) .o_btn_icon .fa-undo",
            run: "click",
        },
        {
            content: "Open add quantity to enter 10 units this time",
            trigger: ".o_mrp_record_line:nth-child(3) .o_btn_icon .fa-pencil",
            run: "click",
        },
        { trigger: ".modal-content input.o_input:value(8)", run: "edit 10" },
        { trigger: ".modal-content footer.modal-footer button.btn-primary", run: "click" },
        { trigger: ".o_line_value.text-danger .o_mrp_record_line_qty:contains(10 / 8)" },
        { trigger: ".o_mrp_record_line:nth-child(3) .o_line_label.text-decoration-line-through" },
        {
            content: "Register not tracked components and continue production",
            trigger: "body:not(:has(.modal)) .o_mrp_record_line:nth-child(4) .fa-check",
            run: "click",
        },
        { trigger: ".o_mrp_record_line:nth-child(4) .fa-plus" },
        {
            content: "Complete last operation",
            trigger: ".o_mrp_record_line:nth-child(7) .fa-check",
            run: "click",
        },
        { trigger: ".o_mrp_record_line:nth-child(7) .fa-undo" },
        {
            content: "Close first operation",
            trigger: '.card-footer button[barcode_trigger="CLWO"]:contains(Mark as Done)',
            run: "click",
        },
        { trigger: ".o_work_center_btn:contains('Savannah) .o_tabular_nums:contains('0')" },

        // PROCESS SECOND WORKORDER
        ...stepUtils.clickOnWorkcenterButton("Jungle"),
        {
            trigger: ".o_mrp_display_record:not(.o_demo)",
            run() {
                helper.assertWorkOrderValues({
                    name: "TWH/MO/00001",
                    operation: "Release",
                    product: "Giraffe",
                    quantity: "2 Units",
                });
            },
        },
        {
            content: "Start the second workorder",
            trigger: 'div.o_mrp_display_record:contains("Release") .card-header',
            run: "click",
        },
        {
            content: "Open the WO setting menu again",
            trigger: '.o_mrp_display_record:contains("Release") .card-footer button.o_btn_icon',
            run: "click",
        },
        {
            content: "Add an operation button",
            trigger: '.modal:not(.o_inactive_modal) button[name="addComponent"]',
            run: "click",
        },
        {
            content: "Ensure the catalog is opened",
            trigger: ".modal:not(.o_inactive_modal) .o_product_kanban_catalog_view",
        },
        {
            content: "search Color",
            trigger: ".modal-body .o_searchview_input",
            run: "edit color",
        },
        {
            trigger: ".o_searchview_autocomplete .o-dropdown-item.focus",
            run: "press Enter",
        },
        {
            content: "Ensure the search is done",
            trigger: '.modal-body div.o_searchview_facet:contains("color")',
        },
        {
            trigger: '.modal-body:not(:has(article.o_kanban_record:not(:contains("Color"))))',
        },
        {
            trigger: '.modal article.o_kanban_record:contains("Color") button .fa-shopping-cart',
            run: "click",
        },
        {
            content: "Ensure the Color product is added",
            trigger: ".modal button .fa-trash",
        },
        {
            content: "Close the catalog",
            trigger: ".modal-header .btn-close",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_mrp_display_record .o_mrp_record_line",
            run() {
                helper.assertWorkOrderValues({
                    name: "TWH/MO/00001",
                    operation: "Release",
                    product: "Giraffe",
                    quantity: "2 Units",
                    steps: [{ label: "Color", value: "1 Unit" }],
                });
            },
        },
        {
            content: "Pause the workorder by scanning the barcode",
            trigger: ".o_mrp_display_record.o_active",
            run: "scan OBTPAUS",
        },
        { trigger: ".o_mrp_display_record:not(.o_active)" },
        {
            content: "Close the WO's Manufacturing Order by scanning the barcode",
            trigger: ".card-footer button[barcode_trigger=CLMO]",
            run: "scan OBTCLMO",
        },
        { trigger: ".o_nocontent_help" },

        // CREATE NEW MO
        // Leave Shop Floor to create a new MO from the Manufacturing app.
        ...stepUtils.closeShopFloor(),
        {
            content: "Switch to Manufacturing",
            trigger: '.o_app[data-menu-xmlid="mrp.menu_mrp_root"]',
            run: "click",
        },
        {
            content: "Pick Production",
            trigger: '.o-dropdown[data-menu-xmlid="mrp.menu_mrp_manufacturing"]',
            run: "click",
        },
        {
            content: "Pick Manufacturing Orders",
            trigger: '.o-dropdown-item[data-menu-xmlid="mrp.menu_mrp_production_action"]',
            run: "click",
        },
        {
            content: "Create an MO",
            trigger: "button.o_list_button_add",
            run: "click",
        },
        {
            content: "Pick a product name",
            trigger: "input#product_id_0",
            run: "edit test_product",
        },
        {
            content: "Create the product",
            trigger: "a#product_id_0_0_0:contains('test_product')",
            run: "click",
        },
        {
            content: "Confirm MO creation",
            trigger: 'button[name="action_confirm"]',
            run: "click",
        },
        {
            content: "Open the Shop Floor directly from the MO",
            trigger: 'button[name="action_open_shop_floor"]',
            run: "click",
        },
        {
            content: "Check the default search filter (filtered by the current MO)",
            trigger: ".o_mrp_display_records",
            run() {
                helper.assertSearchFacets([
                    { label: "Manufacturing Order", value: "TWH/MO/00002" },
                ]);
                helper.assertWorkOrderValues({
                    name: "TWH/MO/00002",
                    product: "test_product",
                    quantity: "1 Unit",
                });
            },
        },
        ...stepUtils.closeShopFloor(),
        // After using to Shopfloor smart button on MO, should ave active WC as overview
        { trigger: ".o_menuitem[href='/odoo/shop-floor']", run: "click" },
        {
            trigger: ".o_work_centers",
            run: () => {
                helper.assertWorkcenterButtons([
                    { name: "Overview", count: 1, active: true },
                    { name: "My WO", count: 0 },
                    { name: "Jungle", count: 0 },
                    { name: "Savannah", count: 0 },
                ]);
            },
        },
        // Leave Shop Floor before to end the tour.
        ...stepUtils.closeShopFloor(),
        { trigger: ".o_apps" },
    ],
});

registry.category("web_tour.tours").add("test_shop_floor_auto_select_workcenter", {
    steps: () => [
        // Select 3 available Work Centers.
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Preparation Table 1"),
        ...stepUtils.addWorkcenterToDisplay("Preparation Table 2"),
        ...stepUtils.addWorkcenterToDisplay("Furnace"),
        ...stepUtils.confirmWorkcentersSelection(),
        {
            trigger: ".o_work_centers",
            run: () => {
                helper.assertWorkcenterButtons([
                    { name: "Overview", count: 2, active: true },
                    { name: "My WO", count: 0 },
                    { name: "Preparation Table 1", count: 1 },
                    { name: "Preparation Table 2", count: 0 },
                    { name: "Furnace", count: 1 },
                ]);
            },
        },
        // Exit the Shop Floor and re-open it: WC buttons should be the same.
        ...stepUtils.closeShopFloor(),
        { trigger: ".o_menuitem[href='/odoo/shop-floor']", run: "click" },
        {
            trigger: ".o_work_centers",
            run: () => {
                helper.assertWorkcenterButtons([
                    { name: "Overview", count: 2, active: true },
                    { name: "My WO", count: 0 },
                    { name: "Preparation Table 1", count: 1 },
                    { name: "Preparation Table 2", count: 0 },
                    { name: "Furnace", count: 1 },
                ]);
            },
        },
        // Finally check selectedWorkCenter preserved when coming back to Shop Floor via breadcrumbs
        ...stepUtils.clickOnWorkcenterButton("Furnace"),
        { trigger: ".o_mrp_display_record .card-footer button.o_btn_icon", run: "click" },
        { trigger: 'button[name="openMO"]', run: "click" },
        { trigger: ".o_breadcrumb a:contains('Shop Floor')", run: "click" },
        {
            trigger: ".o_work_centers",
            run: () => {
                helper.assertWorkcenterButtons([
                    { name: "Overview", count: 2 },
                    { name: "My WO", count: 0 },
                    { name: "Preparation Table 1", count: 1 },
                    { name: "Preparation Table 2", count: 0 },
                    { name: "Furnace", count: 1, active: true },
                ]);
            },
        },
        // Exit the Shop Floor and open it from a WO form view.
        ...stepUtils.closeShopFloor(),
        { trigger: ".o_menuitem[href='/odoo/work-centers']", run: "click" },
        { trigger: "button[data-menu-xmlid='mrp.menu_mrp_manufacturing']", run: "click" },
        { trigger: "a[data-menu-xmlid='mrp.menu_mrp_workorder_todo']", run: "click" },
        { trigger: "[name='workcenter_id'][data-tooltip='Furnace']", run: "click" },
        { trigger: "button[name='action_open_mes']", run: "click" },
        // Check whatever was selected, when we come from a WO form view, only its WC is displayed.
        {
            trigger: ".o_action.o_mrp_display",
            run: () => {
                helper.assertWorkcenterButtons([{ name: "Furnace", count: 1, active: true }]);
            },
        },
    ],
});

registry.category("web_tour.tours").add("test_shop_floor_my_wo_filter_with_pin_user", {
    steps: () => [
        // Select the right workcenter.
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Winter's Workshop"),
        ...stepUtils.confirmWorkcentersSelection(),
        // Open the employee panel and add both employees.
        { trigger: 'button.o_work_center_btn:contains("Winter\'s Workshop")' },
        ...stepUtils.openEmployeesList(),
        ...stepUtils.addEmployee("John Snow"),
        ...stepUtils.addEmployee("Queen Elsa"),
        { trigger: ".modal-footer button.btn-primary", run: "click" },
        // Select the first one => The employee is selected.
        {
            trigger: ".o_mrp_employees_panel li:contains('John Snow'):not(.o_admin_user)",
            run: "click",
        },
        { trigger: ".o_mrp_employees_panel li:contains('John Snow').o_admin_user" },
        // Select the second one => Her PIN code must be entered before to be selected.
        {
            trigger: ".o_mrp_employees_panel li:contains('Queen Elsa'):not(.o_admin_user)",
            run: "click",
        },
        ...stepUtils.enterPIN("41213"),
        { trigger: ".o_mrp_employees_panel li.o_admin_user:contains('Queen Elsa')" },
        ...stepUtils.clickOnWorkcenterButton("Winter's Workshop"),
        {
            content: "Start the first WO with the second employee",
            trigger: ".o_mrp_display_record:contains(TWH/MO/00001) .card-title",
            run: "click",
        },
        { trigger: ".o_mrp_display_record:contains(TWH/MO/00001).o_active" },
        { trigger: ".o_mrp_employees_panel li:contains(John Snow)", run: "click" },
        { trigger: ".o_admin_user:contains(John Snow)" },
        {
            content: "Start the second WO with the first employee",
            trigger: ".o_mrp_display_record:contains(TWH/MO/00002) .card-title",
            run: "click",
        },

        { trigger: ".o_mrp_display_record:contains('TWH/MO/00002').o_active" },
        ...stepUtils.clickOnWorkcenterButton("My WO"),
        // Check the right WO is displayed.
        {
            trigger:
                ".o_mrp_display_content:not(:has(.o_mrp_display_record:contains(TWH/MO/00001)))",
            run: () => {
                const currentEmployeeEl = document.querySelector(".o_admin_user div span.fw-bold");
                assert(currentEmployeeEl.innerText, "John Snow");
                const records = helper.getRecords();
                assert(records.length, 1);
                helper.assertWorkOrderValues({
                    index: 0,
                    name: "TWH/MO/00002",
                    operation: "Build the Snowman",
                    product: "Snowman",
                    quantity: "5 Units",
                    steps: [
                        { label: "Snowball", value: "15 Units" },
                        { label: "Carrot", value: "5 Units" },
                    ],
                });
            },
        },
        // Select the second employee and check only the right WO is shown.
        { trigger: ".o_mrp_employees_panel li:contains(Queen Elsa)", run: "click" },
        ...stepUtils.enterPIN("41213"),
        { trigger: ".o_admin_user:contains(Queen Elsa)" },
        {
            trigger: ".o_mrp_display_record:contains(TWH/MO/00001)",
            run: () => {
                const currentEmployeeEl = document.querySelector(".o_admin_user div span.fw-bold");
                assert(currentEmployeeEl.innerText, "Queen Elsa");
                const records = helper.getRecords();
                assert(records.length, 1);
                helper.assertWorkOrderValues({
                    index: 0,
                    name: "TWH/MO/00001",
                    operation: "Build the Snowman",
                    product: "Snowman",
                    quantity: "3 Units",
                    steps: [
                        { label: "Snowball", value: "9 Units" },
                        { label: "Carrot", value: "3 Units" },
                    ],
                });
            },
        },
        // Select again the first employee and check again only its WO is displayed.
        { trigger: ".o_mrp_employees_panel li:contains(John Snow)", run: "click" },
        { trigger: ".o_admin_user:contains(John Snow)" },
        {
            trigger: ".o_mrp_display_record:contains(TWH/MO/00002)",
            run: () => {
                const currentEmployeeEl = document.querySelector(".o_admin_user div span.fw-bold");
                assert(currentEmployeeEl.innerText, "John Snow");
                const records = helper.getRecords();
                assert(records.length, 1);
                helper.assertWorkOrderValues({
                    index: 0,
                    name: "TWH/MO/00002",
                    operation: "Build the Snowman",
                    product: "Snowman",
                    quantity: "5 Units",
                    steps: [
                        { label: "Snowball", value: "15 Units" },
                        { label: "Carrot", value: "5 Units" },
                    ],
                });
            },
        },
    ],
});

registry.category("web_tour.tours").add("test_generate_serials_in_shopfloor", {
    steps: () => [
        {
            content: "Make sure workcenter is available",
            trigger: '.form-check:has(input[name="Assembly Line"])',
            run: "click",
        },
        {
            trigger: '.form-check:has(input[name="Assembly Line"]:checked)',
        },
        {
            content: "Confirm workcenter",
            trigger: 'button:contains("Confirm")',
            run: "click",
        },
        {
            content: "Select workcenter",
            trigger: 'button.btn-light:contains("Assembly Line")',
            run: "click",
        },
        {
            content: "Open the wizard",
            trigger: '.o_mrp_record_line .text-truncate:contains("Register byprod")',
            run: "click",
        },
        {
            content: "Open the serials generation wizard",
            trigger: ".o_widget_generate_serials button",
            run: "click",
        },
        {
            content: "Input a serial",
            trigger: "#next_serial_0",
            run: "edit 00001",
        },
        {
            content: "Generate the serials",
            trigger: 'button.btn-primary:contains("Generate")',
            run: "click",
        },
        {
            content: "Save and close the wizard",
            trigger: '.o_form_button_save:contains("Save")',
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:first .o_mrp_record_line.text-muted:contains(Register byprod)",
        },
        {
            content: "Set production as done",
            trigger: 'button.btn-primary:contains("Close Production")',
            run: "click",
        },
    ],
});

registry.category("web_tour.tours").add("test_partial_backorder_with_multiple_operations", {
    steps: () => [
        // Make sure workcenter is available.
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Assembly Line"),
        ...stepUtils.confirmWorkcentersSelection(),
        {
            content: "Select workcenter",
            trigger: 'button.btn-light:contains("Assembly Line")',
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(MOBACK-002)) .o_quantity:contains(3 Units)",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(MOBACK-002)) button:contains(Mark as Done)",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(MOBACK-002)) .o_quantity:contains(5 Units)",
        },
    ],
});

registry.category("web_tour.tours").add("test_change_qty_produced", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("WorkCenter"),
        ...stepUtils.confirmWorkcentersSelection(),
        ...stepUtils.clickOnWorkcenterButton("WorkCenter"),
        {
            content: "Register the production (automatically set it as 5/5 Units produced)",
            trigger: ".o_mrp_record_line:contains('Register Production')",
            run: "click",
        },
        {
            content: "Handle MrpRegisterProductionDialog",
            trigger: ".btn-primary:contains('Validate')",
            run: "click",
        },
        {
            content: "Open the wizard and decrease the produced quantity",
            trigger:
                ".o_mrp_record_line .text-decoration-line-through:contains('Register Production')",
            run: "click",
        },
        {
            content: "Edit the quantity producing",
            trigger: 'input[inputmode="decimal"]',
            run: "edit 3",
        },
        {
            content: "Validate",
            trigger: 'button.btn-primary:contains("Validate")',
            run: "click",
        },
        {
            content: "Waiting modal to close",
            trigger: "body:not(:has(.o_dialog))",
        },
        {
            content: "Mark the WorkOrder as Done",
            trigger: 'button.btn-secondary:contains("Close Production")',
            run: "click",
        },
        {
            content: "Confirm consumption warning",
            trigger: 'button.btn-primary:contains("Confirm")',
            run: "click",
        },
        {
            content: "Dismiss backorder",
            trigger: 'button.btn-secondary:contains("No Backorder")',
            run: "click",
        },
        {
            content: "Check that there are no open work orders",
            trigger: ".o_nocontent_help",
        },
    ],
});

registry.category("web_tour.tours").add("test_mrp_manual_consumption_in_shopfloor", {
    steps: () => [
        {
            trigger: ".form-check:has(input[name='Nuclear Workcenter'])",
            run: "click",
        },
        {
            trigger: '.form-check:has(input[name="Nuclear Workcenter"]:checked)',
        },
        {
            trigger: "button:contains('Confirm')",
            run: "click",
        },
        {
            trigger: "button.btn-light:contains('Nuclear Workcenter')",
            run: "click",
        },
        {
            trigger: ".o_control_panel button.active:contains('Nuclear Workcenter')",
        },
        {
            trigger: "span.o_finished_product:contains('Finish')",
            run: "click",
        },
        {
            trigger: ".o_mrp_display_record.o_active",
        },
        {
            trigger: ".o_mrp_record_line:not(.text-muted) span:contains('Component')",
        },
    ],
});

registry.category("web_tour.tours").add("test_component_registration_on_split_productions", {
    steps: () => [
        ...stepUtils.addWorkcenterToDisplay("Lovely Workcenter"),
        ...stepUtils.confirmWorkcentersSelection(),
        {
            content: "Swap to the WO view of the Lovely Workcenter",
            trigger: ".o_control_panel button:contains(Lovely Workcenter)",
            run: "click",
        },
        {
            content: "Open register production",
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO1)) .accordion button:contains('Instructions')",
            run: "click",
        },
        {
            trigger: ".o_data_row:contains(SN002) .o_list_record_remove button",
            run: "click",
        },
        {
            trigger: ".modal-content .o_field_widget[name='quant_id']:contains(SN001)",
            run: "click",
        },
        {
            trigger: ".modal-content .o_field_widget[name='quant_id'] input",
            run: "edit SN003",
        },
        {
            trigger: ".dropdown-item:contains(SN003)",
            run: "click",
        },
        {
            trigger: ".modal-content .modal-header",
            run: "click",
        },
        {
            trigger: ".modal-content .o_field_widget[name='quant_id']:contains(SN003)",
            run() {},
        },
        {
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "Check that the component registration has been completed",
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO1)) button:contains(Mark as Done)",
            run() {},
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO1)) .o_mrp_record_line:contains(Register Production) button.fa-plus",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO1)) .o_mrp_record_line:has(.text-decoration-line-through:contains(Register Production)) span:contains(00)",
            run() {},
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO1)) button:contains(Mark as Done)",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO1)) button:contains(Close Production)",
            run: "click",
        },
        {
            content: "Check that the production was splitted",
            trigger: ".o_mrp_display_record:has(.card-title:contains(SMO1-002))",
            run() {},
        },
        // Process the operations for SMO2 in reverse order and consume more than expected
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO2)) .o_mrp_record_line:contains(Register Production) button.fa-plus",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO2)) .o_mrp_record_line:has(.text-decoration-line-through:contains(Register Production)) span:contains(00)",
            run() {},
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO2)) .accordion button:contains('Instructions')",
            run: "click",
        },
        {
            trigger: ".modal-content .o_field_widget[name='quant_id']:contains(SN004)",
            run: "click",
        },
        {
            trigger: ".modal-content .o_field_widget[name='quant_id'] input",
            run: "edit SN006",
        },
        {
            trigger: ".dropdown-item:contains(SN006)",
            run: "click",
        },
        {
            trigger: ".modal-content .modal-header",
            run: "click",
        },
        {
            trigger: ".modal-content .o_field_widget[name='quant_id']:contains(SN006)",
            run() {},
        },
        {
            trigger: ".modal-content .o_field_widget[name='quant_id']:not(:contains(SN006))",
            run: "click",
        },
        {
            trigger: ".modal-content .o_field_widget[name='quant_id'] input",
            run: "edit SN005",
        },
        {
            trigger: ".dropdown-item:contains(SN005)",
            run: "click",
        },
        {
            trigger: ".modal-content .modal-header",
            run: "click",
        },
        {
            trigger: ".modal-content .o_field_widget[name='quant_id']:contains(SN005)",
            run() {},
        },
        {
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO2)) button:contains(Mark as Done)",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO2)) button:contains(Close Production)",
            run: "click",
        },
        {
            trigger:
                ".modal-content:has(.modal-title:contains(Consumption Warning)) button[name=action_confirm]",
            run: "click",
        },
        {
            content: "Check that the production was splitted",
            trigger: ".o_mrp_display_record:has(.card-title:contains(SMO2-002))",
            run() {},
        },
    ],
});

registry.category("web_tour.tours").add("test_operator_assigned_to_all_work_orders", {
    steps: () => [
        // Select workcenter for the station
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Workcenter1"),
        ...stepUtils.confirmWorkcentersSelection(),
        //Open the employee panel, select Anita Olivier, close the selector
        ...stepUtils.openEmployeesList(),
        ...stepUtils.addEmployee("Anita Olivier"),
        { trigger: ".modal-footer button.btn-primary", run: "click" },
        // Select Anita Olivier in the side panel
        { trigger: ".o_mrp_employees_panel li:contains(Anita Olivier)", run: "click" },
        { trigger: ".o_mrp_employees_panel li:contains(Anita Olivier).o_admin_user", run() {} },
        // Switch to Workcenter1
        ...stepUtils.clickOnWorkcenterButton("Workcenter1"),
        // Complete both operations
        {
            trigger:
                ".o_mrp_display_record:has(.card-header:contains(OP1)) button:contains(Mark as Done)",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-header:contains(OP2)) button:contains(Close Production)",
            run: "click",
        },
        { trigger: ".o_nocontent_help", run() {} },
    ],
});

registry.category("web_tour.tours").add("test_automatic_backorder_no_redirect", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Workcenter1"),
        ...stepUtils.confirmWorkcentersSelection(),
        // Switch to Workcenter1
        ...stepUtils.clickOnWorkcenterButton("Workcenter1"),
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(MOBACK)) .o_mrp_record_line:contains('Register Production')",
            run: "click",
        },
        {
            trigger: ".modal-content .o_field_widget[name=qty_done] input",
            run: "edit 1",
        },
        {
            trigger: ".modal-content button:contains(Validate)",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(MOBACK)) button:contains(Close Production)",
            run: "click",
        },
        {
            trigger: ".o_mrp_display_record:has(.card-title:contains(MOBACK-002))",
            run: () => {
                const records = [...document.querySelectorAll(".o_mrp_display_record")].filter(
                    (rec) => rec.querySelector(".card-title").innerText.includes("MOBACK")
                );
                assert(records.length, 1);
            },
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(MOBACK-002)) .o_mrp_record_line:contains(Register Production)",
            run: "click",
        },
        {
            trigger: ".modal-content button:contains(Validate)",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(MOBACK-002)) button:contains(Close Production)",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display:not(:has(.o_mrp_display_record:has(.card-title:contains(MOBACK))))",
            run: () => {},
        },
    ],
});

registry.category("web_tour.tours").add("test_shop_floor_access", {
    steps: () => [
        {
            trigger: ".o_app:contains(Shop Floor)",
            run: "click",
        },
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Workcenter1"),
        ...stepUtils.confirmWorkcentersSelection(),
        ...stepUtils.openEmployeesList(),
        {
            content: "scan a badge",
            trigger: ".modal-body .o_mrp_operatos_dialog",
            run: "scan 659898105101",
        },
    ],
});

registry.category("web_tour.tours").add("test_shop_floor_unsynced_bom", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("WorkCenter"),
        ...stepUtils.confirmWorkcentersSelection(),
        ...stepUtils.clickOnWorkcenterButton("WorkCenter"),
        {
            content: "Find the COMP1 line",
            trigger: '.o_mrp_record_line:contains("COMP1")',
        },
        {
            content: "Mark the WorkOrder as Done",
            trigger: 'button.btn-secondary:contains("Mark as Done")',
            run: "click",
        },
        {
            content: "Check if the COMP2 line appeared",
            trigger: '.o_mrp_record_line:contains("COMP2")',
        },
        {
            content: "Register the production (automatically set it as 5/5 Units produced)",
            trigger: ".o_mrp_record_line:contains('Register Production')",
            run: "click",
        },
        {
            content: "Handle MrpRegisterProductionDialog",
            trigger: ".btn-primary:contains('Validate')",
            run: "click",
        },
        {
            content: "Close the production order",
            trigger: 'button.btn-secondary:contains("Close Production")',
            run: "click",
        },
        {
            content: "Confirm consumption warning",
            trigger: 'button.btn-primary:contains("Confirm")',
            run: "click",
        },
        {
            content: "Check that there are no open work orders",
            trigger: ".o_nocontent_help",
        },
    ],
});

registry.category("web_tour.tours").add("test_product_consumption", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Workcenter1"),
        ...stepUtils.confirmWorkcentersSelection(),
        ...stepUtils.clickOnWorkcenterButton("Workcenter1"),
        {
            content: "Click on consumption button",
            trigger: '.o_mrp_record_line button.btn .fa-plus',
            run: "click",
        },
        {
            content: "Select first lot",
            trigger: '.o_data_row .o_data_cell[data-tooltip="Lot 1"]',
            run: "click",
        },
        {
            content: "Close the production order",
            trigger: 'button.btn-primary:contains("Close Production")',
            run: "click",
        },
        {
            content: "Check that there are no open work orders",
            trigger: ".o_nocontent_help",
        },
    ]
})
