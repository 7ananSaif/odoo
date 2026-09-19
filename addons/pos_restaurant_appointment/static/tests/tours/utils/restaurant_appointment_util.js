import { negate } from "@point_of_sale/../tests/generic_helpers/utils";

export function appointmentLabel(table_num, appointment_name) {
    return [
        {
            content: `Appointment label ${appointment_name}, is present underneath table ${table_num}`,
            trigger: `.floor-map .table:has(.label:contains("${table_num}")):has(.appointment-label:contains("${appointment_name}"))`,
        },
    ];
}

export function checkTableOption(tableText) {
    return {
        content: `Check that table option ${tableText} is present`,
        trigger: `.o_form_renderer .o-autocomplete--dropdown-menu li a.dropdown-item:contains("${tableText}")`,
    };
}

export function selectTable(tableText) {
    return {
        content: `Select table option containing ${tableText}`,
        trigger: `.o_form_renderer .o-autocomplete--dropdown-menu li a.dropdown-item:contains("${tableText}")`,
        run: "click",
    };
}

export function checkAppointment(appointmentName) {
    return {
        content: `Check that appointment ${appointmentName} is visible in Kanban`,
        trigger: `.o_kanban_record:contains("${appointmentName}")`,
    };
}

export function checkAppointmentNotVisible(appointmentName) {
    return {
        content: `Check that appointment ${appointmentName} is not visible`,
        trigger: negate(`.o_kanban_record:contains("${appointmentName}")`),
    };
}

export function checkAppointmentLabelNotPresent(table_num, appointment_name) {
    return [
        {
            content: `Appointment "${appointment_name}" should NOT appear under table ${table_num}`,
            trigger: negate(
                `.appointment-label:contains("${appointment_name}")`,
                `.table:has(.label:contains("${table_num}"))`
            ),
        },
    ];
}

export function isKanbanViewShown() {
    return {
        content: "Check that the booking kanban view is shown",
        trigger: ".pos-content .o_action_manager .o_kanban_view",
    };
}
