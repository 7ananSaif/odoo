import { delay } from "@web/core/utils/concurrency";
import { registry } from "@web/core/registry";
import * as tourUtils from '@website_sale/js/tours/tour_utils';


function getFutureDate(days) {
    days = (days ?? 0) + 7;
    return luxon.DateTime.now().set({ weekday: 1 }).plus({ days }).toFormat('MM/dd/yyyy');
}

registry.category("web_tour.tours").add("rental_cart_update_duration", {
    url: "/shop",
    steps: () => [
        ...tourUtils.searchProduct("computer", { select: true }),
        {
            content: "Wait for the daterange picker to be initialized",
            trigger: '.o_daterange_picker[data-has-default-dates]',
        },
        {
            content: "Open daterangepicker",
            trigger: "input[name=renting_start_date]",
            run: "click",
        },
        {
            content: "Wait for the datepicker to be opened",
            trigger: ".o_time_picker_input",
        },
        {
            content: "Pick start time",
            trigger: ".o_time_picker_input:eq(0)",
            run: "edit 6:00 && press Enter",
        },
        {
            content: "Pick end time",
            trigger: ".o_time_picker_input:eq(1)",
            run: "edit 12:00 && press Enter",
        },
        {
            content: "click on add to cart",
            trigger:
                '#product_detail form #add_to_cart',
            run: "click",
        },
        tourUtils.goToCart(),
        {
            content: "Verify Rental Product is in the cart",
            trigger: '#cart_products div div.css_quantity input[value="1"]',
        },
        {
            content: "Open daterangepicker",
            trigger: "input[name=renting_start_date]",
            run: "click",
        },
        {
            content: "Wait for the datepicker to be opened",
            trigger: ".o_time_picker_input",
        },
        {
            content: "Pick start time",
            trigger: ".o_time_picker_input:eq(0)",
            run: "edit 8:00 && press Enter && press Escape",
        },
        {
            content: "Verify order line rental period start time",
            trigger: 'div.text-muted.small span:contains("8:00")',
        },
        {
            content: "Verify order line rental period return time",
            trigger: 'div.text-muted.small span:contains("12:00")',
        },
    ],
});

registry.category('web_tour.tours').add('date_based_rental_duration', {
    steps: () => [
        ...tourUtils.searchProduct("Computer", { select: true }),
        {
            content: "Wait for the daterange picker to be initialized",
            trigger: '.o_daterange_picker[data-has-default-dates]',
        },
        {
            content: "Select the return date",
            trigger: 'input[name=renting_end_date]',
            async run(helpers) {
                await delay(1000);
                await helpers.edit(getFutureDate(2));
                await helpers.press("Tab");
            },
        },
        {
            content: "Rent for 2 days",
            trigger: 'input[name=renting_start_date]',
            async run(helpers) {
                await delay(1000);
                await helpers.edit(getFutureDate(1));
                await helpers.press("Tab");
            },
        },
        {
            content: "Add to cart",
            trigger: '#product_detail form #add_to_cart',
            run: 'click',
        },
        {
            content: "Rental duration should display 2 days",
            trigger: 'span.o_renting_details:contains(2 Days)',
        },
        tourUtils.goToCart(),
        {
            content: "Wait for cart to load",
            trigger: '#shop_cart',
        },
        ...tourUtils.assertCartAmounts({ untaxed: "40.00" }), // $ 20.00 per day
    ],
});
