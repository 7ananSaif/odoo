/* @odoo-module */

export const stepUtils = {
    // Workcenters' utils.
    openWorkcentersSelector() {
        return [
            {
                content: "Open Workcenter selection dialog",
                trigger: ".o_mrp_display_onboarding_button_container button.btn-primary",
                run: "click",
            },
        ];
    },
    addWorkcenterToDisplay(workcenterName) {
        const target = `.o_mrp_workcenter_dialog div.o_workcenter_button:contains("${workcenterName}") input`;
        return [
            { trigger: `${target}:not(:checked)`, run: "click" },
            { trigger: `${target}:checked` },
        ];
    },
    confirmWorkcentersSelection() {
        return [
            {
                content: "Confirm Workcenter selection",
                trigger: "footer.modal-footer button.btn-primary",
                run: "click",
            },
        ];
    },
    clickOnWorkcenterButton(workcenterName) {
        const target = `.o_work_centers_container button.o_work_center_btn:contains("${workcenterName}")`;
        return [
            { trigger: `${target}:not(.active)`, run: "click" },
            { trigger: `${target}.active` },
        ];
    },
    // Employees' utils.
    openEmployeesList() {
        return [
            { trigger: "button.o_edit_operators", run: "click" },
            { trigger: ".modal-body .o_mrp_operatos_dialog" },
        ];
    },
    addEmployee(employee) {
        return [
            {
                trigger: `.modal-body .o_mrp_operatos_dialog li[name='${employee}']:not(.active)`,
                run: "click",
            },
            { trigger: `.o_mrp_operatos_dialog li[name='${employee}'].active` },
        ];
    },
    enterPIN(code) {
        const steps = [];
        for (const c of code) {
            steps.push({
                trigger: `.popup-numpad button:contains(${c})`,
                run: "click",
            });
        }
        steps.push({
            trigger: `.popup-input:contains('${"".padEnd(code.length, "•")}')`,
        });
        steps.push({
            trigger: "footer .btn-primary",
            run: "click",
        });
        return steps;
    },
    // Other utils.
    closeShopFloor() {
        return [
            { trigger: ".o_cp_burger_menu .o_btn_icon", run: "click" },
            { trigger: ".dropdown-menu.show button:contains('Close')", run: "click" },
        ];
    },
};
