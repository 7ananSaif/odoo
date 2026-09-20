import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

registry
    .category("web_tour.tours")
    .add("change_contract_template_on_offer_tour", {
        //url: "/odoo/employees/<employee_id>",
        steps: () => ([
                {
                    trigger: 'button[name="action_generate_offer"]',
                    content: 'Click on "Offer" smart button',
                    run: "click",
                },
                {
                    trigger: "#contract_template_id_0",
                    content: 'Click on the "Contract Template" select input',
                    run: "click",
                },
                {
                    trigger: "a:contains(Pokémon Trainer)",
                    content: 'Change "Contract Template" select input\'s value',
                    run: "click",
                },
                ...stepUtils.saveForm(),
            ]),
        },
    );
