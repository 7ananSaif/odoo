import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

const oldWriteText = navigator.clipboard.writeText;

registry.category("web_tour.tours").add('appointment_hr_recruitment_tour', {
    url: '/odoo',
    steps: () => [stepUtils.showAppsMenuItem(), {
        trigger: '.o_app[data-menu-xmlid="hr_recruitment.menu_hr_recruitment_root"]',
        run: 'click',
    }, {
        trigger: '.o_kanban_record:contains("Test Job")',
        run: 'click',
    }, {
        trigger: '.o_kanban_record:contains("Test Applicant")',
        run: 'click',
    },{
        trigger: 'button[name="action_create_meeting"]',
        run: 'click',
    }, {
        trigger: 'button.dropdownAppointmentLink',
        run: 'click',
    }, {
        trigger: '.o_appointment_button_link:contains("Test AppointmentHrRecruitment")',
        async run(helpers) {
            // Patch write on clipboard -- go to the url (to then book an appointment from there
            navigator.clipboard.writeText = (text) => {window.location.href = text};
            await helpers.click();
        },
        expectUnloadPage: true,
    }, {
        trigger: '.o_slot_hours:contains("4")',
        run: 'click',
        expectUnloadPage: true,
    }, {
        trigger: 'input[name="name"]',
        run: 'edit Ana Tourelle',
    }, {
        trigger: 'input[name="email"]',
        run: 'edit ana@example.com',
    }, {
        trigger: 'input[type="phone"]',
        run: 'edit 3141592',
    }, {
        trigger: '.o_appointment_form_confirm_btn',
        run: 'click',
        expectUnloadPage: true,
    }, {
        trigger: '.fa-check-circle',
        async run(helpers) {
            await helpers.click();
            // Re-patch the function with the previous writeText
            navigator.clipboard.writeText = oldWriteText;
        },
    }],
});
