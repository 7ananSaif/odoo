import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add('test_carrier_type_selection_field', { steps: () => [
    {
        content: 'Show the carrier type popup',
        trigger: 'button[name="action_get_carrier_type"]',
        run: 'click'
    },
    {
        content: 'Open the selection',
        trigger: 'input#carrier_type_0',
        run: 'click'
    },
    {
        content: 'Check if the dropdown was populated',
        trigger: '.o_field_selection_menu',
        run: function () {
            const carrierTypeChoices = [...document.querySelectorAll(".o_field_selection_menu span")].map(e=>e.textContent);
            [
                "FedEx",
                "DHL Global Mail",
                "USPS",
                "GSO",
                "DHL Express",
                "Canada Post",
                "Canpar",
                "DPD",
                "LSO",
                "UPSDAP",
            ].forEach((carrierType) => {
                console.info(`Checking carrier type ${carrierType} ...`);
                const index = carrierTypeChoices.indexOf(carrierType);
                if (index === -1) {
                    console.error(`${carrierType} value not found in available carrier types.`);
                }
            })
        }
    },
        {
            trigger: ".o-dropdown-item:contains(FedEx)",
            run: "click",
        },
        {
            content: "Check that the selected value is visible",
            trigger: ".o_field_carrier_type_selection input:value(Fedex)",
        },
        {
            trigger: ".btn:contains(Cancel)",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal-header:contains('Select a carrier')))",
        },
]});
