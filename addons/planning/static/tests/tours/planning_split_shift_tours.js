import { registry } from "@web/core/registry";

async function splitPill(helpers, index = 0) {
    const pillEl = helpers.anchor;
    if (pillEl.parentElement.dataset.pillId === "__pill__8") {
        pillEl.scrollIntoView({ block: "end" });
        await new Promise(requestAnimationFrame);
    }
    const style = getComputedStyle(pillEl.parentElement); // wrapper style
    const first = +style.getPropertyValue("grid-column-start").slice(1);
    const last = +style.getPropertyValue("grid-column-end").slice(1);
    const span = last - first;
    const { width, height } = pillEl.getBoundingClientRect();
    const position = { x: ((index + 1) * width) / span, y: height / 2 };
    await helpers.hover(pillEl, { position, relative: true });
    await new Promise(requestAnimationFrame);
    helpers.click(pillEl, { position, relative: true });
}

registry.category("web_tour.tours").add('planning_split_shift_week', {
    url: '/odoo?debug=tests',
    steps: () => [{
    trigger: '.o_app[data-menu-xmlid="planning.planning_menu_root"]',
    content: "Let's start managing your employees' schedule!",
    tooltipPosition: 'bottom',
    run: "click",
}, {
    trigger: '.o_gantt_renderer_controls .dropdown-toggle:contains("Week")',
    content: "The initial default range should be week",
}, {
    isActive: [
        "body:has(.o_gantt_pill_wrapper[data-pill-id='__pill__1'] .o_gantt_pill:contains(10:00 AM - 11:00 AM))",
    ],
    trigger: ".o_gantt_pill_wrapper[data-pill-id='__pill__1'] .o_gantt_pill:contains(10:00 AM - 11:00 AM)",
    async run({ click, waitFor }) {
        await click();
        await waitFor(`.o_popover`, { timeout: 2000 });
        await click(`.o_popover button:contains(delete)`);
        await waitFor(`.modal`, { timeout: 2000 });
        await click(`.modal button:contains(delete)`);
    }
}, {
    trigger: "body:not(:has(.o_gantt_pill_wrapper[data-pill-id='__pill__1'] .o_gantt_pill:contains(10:00 AM - 11:00 AM)))",
}, {
    trigger: ".o_searchview_dropdown_toggler",
    content: "Open Filter",
    run: "click",
}, {
    trigger: ".o_add_custom_filter",
    content: "Click on custom filter",
    run: "click",
}, {
    trigger: ".o_model_field_selector",
    content: "Write domain excluding open shifts",
    run() {
        const input = document.querySelector(".o_domain_selector_debug_container textarea")
        input.value = '[("resource_id", "!=", False)]';
        input.dispatchEvent(new Event("change", { bubbles: true, cancelable: false }));
    }
}, {
    trigger: ".modal-footer > .btn-primary",
    content: "Add custom filter",
    run: "click",
}, {
    trigger: ".o_searchview_input",
    content: "Search planning shifts assigned to Aramis",
    run: "fill Aramis",
}, {
    trigger: ".o_searchview_autocomplete .o-dropdown-item > a:not(.o_expand)",
    content: "Select filter resource = Aramis",
    run: 'click',
}, {
    trigger: ".o_searchview_facet:last:contains(Aramis)"
}, {
    trigger: ".o_gantt_row_headers:has(.o_gantt_row_header:contains(Aramis))",
}, {
    trigger: ".o_searchview_input",
    content: "Search planning shifts assigned to Athos",
    run: "fill Athos",
}, {
    trigger: ".o_searchview_autocomplete .o-dropdown-item > a:not(.o_expand)",
    content: "Select filter resource = Athos",
    run: 'click',
}, {
    trigger: ".o_searchview_facet:last:contains(Aramis):contains(Athos)"
}, {
    trigger: ".o_gantt_row_headers:has(.o_gantt_row_header:contains(Athos))",
}, {
    trigger: ".o_searchview_input",
    content: "Search planning shifts assigned to Porthos",
    run: "fill Porthos",
}, {
    trigger: ".o_searchview_autocomplete .o-dropdown-item > a:not(.o_expand)",
    content: "Select filter resource = Porthos",
    run: 'click',
}, {
    trigger: ".o_searchview_facet:last:contains(Aramis):contains(Athos):contains(Porthos)"
}, {
    trigger: ".o_gantt_row_headers:has(.o_gantt_row_header:contains(Porthos))",
}, {
    trigger: ".o_searchview_input",
    content: "Search planning shifts assigned to Rochefort",
    run: "fill Rochefort",
}, {
    trigger: ".o-dropdown-item > a:not(.o_expand)",
    content: "Select filter resource = Rochefort",
    run: 'click',
}, {
    trigger: ".o_searchview_facet:last:contains(Aramis):contains(Athos):contains(Porthos):contains(Rochefort)"
}, {
    trigger: ".o_gantt_row_headers:has(.o_gantt_row_header:contains(Rochefort)):has(.o_gantt_row_header:contains(Porthos)):has(.o_gantt_row_header:contains(Athos)):has(.o_gantt_row_header:contains(Aramis))",
}, {
    trigger: ".o_gantt_cells .o_gantt_pill_wrapper:eq(3)",
    content: "Wait for 4 pills to be displayed",
},
{
    trigger: ".o_gantt_pill_wrapper[data-pill-id='__pill__1'] .o_gantt_pill",
    content: "Split the slot assigned to Aramis after one day",
    async run(helpers) {
        await splitPill(helpers, 0);
    }
}, {
    trigger: ".o_gantt_pill_wrapper[data-pill-id='__pill__5']",
    content: "Wait for the new shift to appear",
}, {
    trigger: ".o_notification_buttons button i[title='Undo']",
    content: "An Undo notification should appear",
}, {
    trigger: ".o_gantt_pill_wrapper[data-pill-id='__pill__3'] .o_gantt_pill",
    content: "Split the slot assigned to Athos after two days",
    async run(helpers) {
        await splitPill(helpers, 1);
    }
}, {
    trigger: ".o_gantt_pill_wrapper[data-pill-id='__pill__6']",
    content: "Wait for the new shift to appear",
}, {
    trigger: ".o_notification_buttons button i[title='Undo']",
    content: "An Undo notification should appear",
}, {
    trigger: ".o_gantt_pill_wrapper[data-pill-id='__pill__3'] .o_gantt_pill",
    content: "Split the first slot assigned to Athos after one day",
    async run(helpers) {
        await splitPill(helpers, 0);
    }
}, {
    trigger: ".o_gantt_pill_wrapper[data-pill-id='__pill__7']",
    content: "Wait for the new shift to appear",
}, {
    trigger: ".o_notification_buttons button i[title='Undo']",
    content: "An Undo notification should appear",
}, {
    trigger: ".o_gantt_pill_wrapper[data-pill-id='__pill__6'] .o_gantt_pill",
    content: "Split the first slot assigned to Porthos after one day",
    async run(helpers) {
        await splitPill(helpers, 0);
    }
}, {
    trigger: ".o_gantt_pill_wrapper[data-pill-id='__pill__8']",
    content: "Wait for the new shift to appear",
}, {
    trigger: ".o_notification_buttons button i[title='Undo']",
    content: "An Undo notification should appear",
}, {
    trigger: ".o_gantt_pill_wrapper[data-pill-id='__pill__8'] .o_gantt_pill",
    content: "Split the first slot assigned to Rochefort on weekend",
    async run(helpers) {
        await splitPill(helpers, 0);
    }
}, {
    trigger: ".o_gantt_pill_wrapper[data-pill-id='__pill__9']",
    content: "Wait for the new shift to appear",
}, {
    trigger: ".o_notification_buttons button i[title='Undo']",
    content: "An Undo notification should appear",
}
]});
