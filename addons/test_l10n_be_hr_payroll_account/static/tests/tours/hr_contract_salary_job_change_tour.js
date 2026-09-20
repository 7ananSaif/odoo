import { registry } from "@web/core/registry";
import { inputFiles } from "@web/../tests/utils";
import { redirect } from "@web/core/utils/urls";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add("hr_contract_salary_tour_job_change", {
    url: "/odoo",
    wait_for: Promise.resolve(odoo.__TipTemplateDef),
    steps: () => [
        /*
         * Generate offer for the employee
         */
        {
            content: "Log into Belgian Company",
            trigger: ".o_menu_systray .o_switch_company_menu button.dropdown-toggle",
            run: "click",
        },
        {
            content: "Log into Belgian Company",
            trigger: ".dropdown-menu .dropdown-item div span:contains('My Belgian Company - TEST')",
            run: "click",
            expectUnloadPage: true,
        },
        {
            trigger:
                ".o_menu_systray .o_switch_company_menu button.dropdown-toggle span:contains('My Belgian Company - TEST')",
        },
        {
            content: "Employees",
            trigger: '.o_app[data-menu-xmlid="hr.menu_hr_root"]',
            run: "click",
        },
        {
            content: "Go on Employee Page",
            trigger: 'span:contains("Jean Jasse")',
            run: "click",
        },
        stepUtils.autoExpandMoreButtons(),
        {
            content: "Generate offer",
            trigger: ".btn:contains(Offers)",
            run: "click",
        },
        {
            content: "Contract Template",
            trigger: ".o_field_widget.o_field_many2one[name=contract_template_id] input",
            run: "edit Senior Developer Template Contract",
        },
        {
            isActive: ["auto"],
            trigger: ".ui-autocomplete > li > a:contains(Senior Developer Template Contract)",
            run: "click",
        },
        {
            content: "Change job position",
            trigger: ".o_input#employee_job_id_0",
            run: "edit Senior Developer BE",
        },
        {
            trigger: "ul.o-autocomplete--dropdown-menu",
        },
        {
            trigger: "a.dropdown-item:contains('Senior Developer BE')",
            run: "click",
        },
        {
            content: "Save Offer",
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            trigger: ".o_form_saved",
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
        /*
         * Unlog and go to the salary configurator page logged in as the employee
         */
        {
            content: "Unlog",
            trigger: ".o-mail-Chatter .o-mail-Message:eq(0) a",
            async run() {
                const offer_link = this.anchor.href;
                // Retrieve the link without the origin to avoid
                // mismatch between localhost:8069 and 127.0.0.1:8069
                // when running the tour with chrome headless
                const regex = "/salary_package/simulation/.*";
                const url = offer_link.match(regex)[0];
                localStorage.setItem("url", url);
                redirect("/web/session/logout");
            },
            expectUnloadPage: true,
        },
        {
            content: "Log as employee - input login",
            trigger: "input#login",
            run: "edit jeanjasse",
        },
        {
            content: "Log as employee - input password",
            trigger: "input#password",
            run: "edit jeanjasse",
        },
        {
            content: "Log as employee",
            trigger: "button[type='submit']",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Go on configurator",
            trigger: ".o_web_client",
            run: function () {
                const url = localStorage.getItem("url");
                redirect(url);
            },
            expectUnloadPage: true,
        },
        {
            content: "wait for the interaction to load",
            trigger: "#hr_contract_salary[is-ready=true]",
        },
        /*
         * We only modify the IP to check if the change is correctly made
         * according to the job change of the employee.
         */
        {
            content: "Take IP",
            trigger: "input[name=ip_value_radio]:eq(1):not(:visible)",
            run: "click",
        },
        // We set internet to show the upload invoice button
        {
            content: "Set Internet",
            trigger: 'input[name="internet_manual"]',
            run: "edit 30",
        },
        {
            content: "sex",
            trigger: "input[name=sex]:not(:visible)",
            run: function () {
                document.querySelector('input[value="female"]').checked = true;
            },
        },
        {
            content: "National Identification Number",
            trigger: 'input[name="identification_id"]',
            run: "edit 11.11.11-111.11",
        },
        {
            content: "Nationality",
            trigger: "select[name=country_id]:not(:visible)",
            run: "selectByLabel Belgium",
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
            content: "Country",
            trigger: "select[name=private_country_id]:not(:visible)",
            run: "selectByLabel Belgium",
        },
        {
            content: "Upload ID card copy (Both Sides)",
            trigger: 'input[name="id_card"]',
            async run() {

                const file = new File(["hello, world"], "employee_id_card.pdf", {
                    type: "application/pdf",
                });
                await inputFiles('input[name="id_card"]', [file]);
            },
        },
        {
            content: "Upload Mobile Subscription Invoice",
            trigger: 'input[name="mobile_invoice"]',
            async run() {
                const file = new File(["hello, world"], "employee_mobile_invoice.pdf", {
                    type: "application/pdf",
                });

                await inputFiles('input[name="mobile_invoice"]', [file]);
            },
        },
        {
            content: "Upload Sim Card Copy",
            trigger: 'input[name="sim_card"]',
            async run() {
                const file = new File(["hello, world"], "employee_sim_card.pdf", {
                    type: "application/pdf",
                });

                await inputFiles('input[name="sim_card"]', [file]);
            },
        },
        {
            content: "Upload Internet Subscription invoice",
            trigger: 'input[name="internet_invoice"]',
            async run() {
                const file = new File(["hello, world"], "employee_internet_invoice.pdf", {
                    type: "application/pdf",
                });
                await inputFiles('input[name="internet_invoice"]', [file]);
            },
        },
        {
            content: "submit",
            trigger: "button#hr_cs_submit",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Next 1",
            trigger: ":iframe .o_sign_sign_item_navigator:contains(Click to start)",
            run: "click",
        },
        {
            content: "Type Date",
            trigger: ":iframe input.ui-selected",
            run: "edit 17/09/2018",
        },
        // fill signature
        {
            content: "Next 2",
            trigger: ":iframe .o_sign_sign_item_navigator:contains(next)",
            run: "click",
        },
        {
            content: "Click Signature",
            trigger: ":iframe button.o_sign_sign_item",
            run: "click",
        },
        {
            content: "Click Auto",
            trigger: ".modal:not(.o_inactive_modal) a.o_web_sign_auto_button:contains(Auto)",
            run: "click",
        },
        {
            content: "Adopt & Sign",
            trigger:
                ".modal:not(.o_inactive_modal) .modal-footer button.btn-primary:enabled:contains(sign all)",
            run: "click",
        },
        {
            content: "Wait modal closed",
            trigger: "body:not(:has(.modal))",
        },
        // fill date
        {
            content: "Next 4",
            trigger: ":iframe .o_sign_sign_item_navigator:contains(next)",
            run: "click",
        },
        {
            content: "Type Date",
            trigger: ":iframe input.ui-selected",
            run: "edit 17/09/2018",
        },
        {
            content: "Validate and Sign",
            trigger: ".o_sign_validate_banner button",
            run: "click",
        },
    ],
});
