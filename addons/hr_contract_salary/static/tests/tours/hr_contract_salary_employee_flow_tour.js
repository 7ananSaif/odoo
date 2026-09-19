import { registry } from "@web/core/registry";
import { redirect } from "@web/core/utils/urls";

export const salaryConfigTourStart = () => [
    {
        content: "Open company menu drop-down",
        trigger: ".o_menu_systray .o_switch_company_menu button.dropdown-toggle",
        run: "click",
    },
    {
        content: "Log into Rambo's Company",
        trigger:
            ".o-dropdown--menu .dropdown-item div span:contains('Rambo Company - TEST')",
        run: "click",
        expectUnloadPage: true,
    },
    {
        trigger:
            ".o_menu_systray .o_switch_company_menu button.dropdown-toggle span:contains('Rambo Company - TEST')",
    },
    {
        content: "Open Employees app",
        trigger: ".o_app[data-menu-xmlid='hr.menu_hr_root']",
        run: 'click',
    },
    {
        content: "Open an Employee Profile",
        trigger: ".o_kanban_record:contains('Ahmed Abdelrazek')",
        run: 'click',
    },
    {
        trigger: ".o_statusbar_buttons",
    },
    {
        content: "Generate Offer",
        trigger: "button[name='action_generate_offer']",
        run: "click",
    },
    {
        content: "Save Offer",
        trigger: ".o_form_button_save",
        run: "click",
    },
    {
        content: "Open compose email wizard",
        trigger: "button[name='action_send_by_email']",
        run: "click",
    },
    {
        content: "Send Offer",
        trigger: "button.o_mail_send",
        run: "click",
    },
    {
        trigger: "button[name='action_jump_to_offer']",
    },
    {
        content: "Go onto configurator",
        trigger: ".o-mail-Chatter .o-mail-Message:eq(0) a",
        async run(helpers) {
            const offer_link = helpers.anchor.href;
            // Retrieve the link without the origin to avoid
            // mismatch between localhost:8069 and 127.0.0.1:8069
            // when running the tour with chrome headless
            const regex = "/salary_package/simulation/.*";
            const url = offer_link.match(regex)[0];
            redirect(url);
        },
        expectUnloadPage: true,
    },
];

export const salaryConfigTourPersonalInfo = () => [
    {
        content: "Birthdate",
        trigger: 'input[name="birthday"]',
        run() {
            this.anchor.value = "2017-09-01";
        },
    },
    {
        content: "Sex",
        trigger: "input[name=sex]:not(:visible)",
        run() {
            document.querySelector('input[value="female"]').checked = true;
        },
    },
    {
        content: "National Identification Number",
        trigger: 'input[name="identification_id"]',
        run: "edit 11.11.11-111.11",
    },
    {
        content: "Street",
        trigger: 'input[name="private_street"]',
        run: "edit New Private Street",
    },
    {
        content: "City",
        trigger: 'input[name="private_city"]',
        run: "edit Louvain-la-Neuve",
    },
    {
        content: "Zip Code",
        trigger: 'input[name="private_zip"]',
        run: "edit 1348",
    },
    {
        content: "Open Private Country Dropdown",
        trigger: "div[name='private_country_id'] div.o-dropdown.dropdown-toggle",
        run: "click"
    },
    {
        content: "Select Option",
        trigger: ".o_select_menu_item div:contains('Egypt')",
        run: "click"
    },
    {
        content: "Email",
        trigger: 'input[name="private_email"]',
        run: "edit ahmed.abdelrazek@example.com",
    },
    {
        content: "Phone Number",
        trigger: 'input[name="private_phone"]',
        run: "edit 1234567890",
    },
    {
        content: "Place of Birth",
        trigger: 'input[name="place_of_birth"]',
        run: "edit Brussels",
    },
            {
        content: "Open Nationality Dropdown",
        trigger: "div[name='country_id'] div.o-dropdown.dropdown-toggle",
        run: "click"
    },
    {
        content: "Nationality",
        trigger: "select[name=country_id]:not(:visible)",
        run: "selectByLabel Belgium",
    },
    {
        id: "certificate_step",
        content: "Certificate",
        trigger: "select[name=certificate]:not(:visible)",
        run: "selectByLabel Master",
    },
    {
        content: "School",
        trigger: 'input[name="study_school"]',
        run: "edit UCL",
    },
    {
        content: "School Level",
        trigger: 'input[name="study_field"]',
        run: "edit Civil Engineering, Applied Mathematics",
    },
    {
        content: "Bank Account",
        trigger: 'input[name="acc_number"]',
        run: "edit BE10 3631 0709 4104",
    },
    {
        content: "Private License Plate",
        trigger: 'input[name="private_car_plate"]',
        run: "edit 1-ABC-123",
    },
    {
        content: "Emergency Contact",
        trigger: 'input[name="emergency_contact"]',
        run: "edit Batman",
    },
    {
        content: "Emergency Phone",
        trigger: 'input[name="emergency_phone"]',
        run: "edit +32 2 290 34 90",
    },
    {
        content: "Country of Birth",
        trigger: "select[name=country_of_birth]:not(:visible)",
        run: "selectByLabel Belgium",
    },
];

export const salaryConfigTourSubmitAndSign = () => [
    {
        content: "Submit",
        trigger: "button#hr_cs_submit",
        run: "click",
        expectUnloadPage: true,
    },
    {
        content: "Fill Date 1",
        trigger: ":iframe input.o_sign_sign_item_default:eq(0)",
        run: "click",

    },
    // fill signature
    {
        content: "Click Signature",
        trigger: ":iframe button.o_sign_sign_item",
        run: "click",
    },
    {
        content: "Click Auto",
        trigger: "a.o_web_sign_auto_button:contains('Auto')",
        run: "click",
    },
    {
        content: "Adopt & Sign",
        trigger: "footer.modal-footer button.btn-primary:enabled",
        run: "click",
    },
    {
        content: "Wait for modal to close",
        trigger: ":iframe body:not(:has(footer.modal-footer button.btn-primary))",
    },
    // fill date
    {
        content: "Type Date",
        trigger: ":iframe input.o_sign_sign_item_default:eq(1)",
        run: "edit 17/09/2018",
    },
    {
        content: "Validate and Sign",
        trigger: ".o_sign_validate_banner button",
        run: "click",
        expectUnloadPage: true,
    },
];

registry.category("web_tour.tours").add("hr_contract_salary_employee_flow_tour", {
    url: "/odoo",
    wait_for: Promise.resolve(odoo.__TipTemplateDef),
    steps: () => [
        ...salaryConfigTourStart(),
        ...salaryConfigTourPersonalInfo(),
        ...salaryConfigTourSubmitAndSign(),        
    ]
});

registry.category("web_tour.tours").add("hr_contract_salary_employee_flow_tour_counter_sign", {
    url: "/odoo",
    wait_for: Promise.resolve(odoo.__TipTemplateDef),
    steps: () => [
        {
            content: "Open company menu drop-down",
            trigger: ".o_menu_systray .o_switch_company_menu button.dropdown-toggle",
            run: "click",
        },
        {
            content: "Log into Rambo's Company",
            trigger:
                ".o-dropdown--menu .dropdown-item div span:contains('Rambo Company - TEST')",
            run: "click",
            expectUnloadPage: true,
        },
        {
            trigger: `.oe_topbar_name:contains(Rambo Company - TEST)`,
        },
        {
        content: "Open Sign app",
        trigger: ".o_app[data-menu-xmlid='sign.menu_document']",
        run: 'click',
        },
        {
            content: "Remove Filter",
            trigger: "button[title='Remove']",
            run: "click",
        },
        {
            content: "Go to Signable Document",
            trigger: "button[name='go_to_signable_document']",
            run: "click",
        },
        {
            content: "Next 1",
            trigger: ":iframe .o_sign_sign_item_navigator",
            run: "click",
        },
        {
            content: "Next 2",
            trigger: ":iframe .o_sign_sign_item_navigator",
            run: "click",
        },
        {
            content: "Click Signature",
            trigger: ":iframe button.o_sign_sign_item",
            run: "click",
        },
        {
            content: "Click Auto",
            trigger: "a.o_web_sign_auto_button:contains('Auto')",
            run: "click",
        },
        {
            content: "Adopt & Sign",
            trigger: "footer.modal-footer button.btn-primary:enabled",
            run: "click",
        },
        {
            trigger: ":iframe body:not(:has(footer.modal-footer button.btn-primary))",
        },
        {
            content: "Validate and Sign",
            trigger: ".o_sign_validate_banner button",
            run: "click",
        },
    ],
});
