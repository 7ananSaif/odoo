import { assert, fail } from "@stock/../tests/tours/tour_helper";
import { patch } from "@web/core/utils/patch";
import { TourHelpers } from "@web_tour/js/tour_automatic/tour_helpers";

patch(TourHelpers.prototype, {
    async scan(barcode) {
        odoo.__WOWL_DEBUG__.root.env.services.barcode.bus.trigger("barcode_scanned", { barcode });
        await new Promise((resolve) => requestAnimationFrame(resolve));
    },
});

// Helper's methods.

/**
 * Get and returns exactly one record (MO or WO), fails if multiple records are found.
 * @param {Object} options
 * @returns {HTMLElement}
 */
export function getRecord(options = {}) {
    const recordEls = getRecords(...arguments);
    if (recordEls.length > 1) {
        fail("Multiple records found for selector.");
    }
    return recordEls[0];
}

/**
 * Get and returns all records matching the given description, fails if no record is found.
 * @param {Object} [options] if no description, will return all the records
 * @returns {Element[]}
 */
export function getRecords(options = {}) {
    const selector = ".o_mrp_display_record:not(.o_demo)";
    const recordsEl = document.querySelectorAll(selector);
    if (recordsEl.length === 0) {
        fail("No record found for selector.");
    }
    return recordsEl;
}

// Assert's methods.

/**
 * Check the given MO has the expected amount of Work Order lines.
 * @param {HTMLElement} productionCard the Manufacturing Order element
 * @param {Number} expectedCount
 */
export function assertProductionWorkorderCount(productionCard, expectedCount) {
    const workorderLinesEl = productionCard.querySelectorAll(".o_mrp_operation_name");
    assert(workorderLinesEl.length, expectedCount, "Not the right amount of WO.");
}

/**
 * Check searchview's facets to ensure current filters match what is expected.
 * @param {Object[]} facetsVals
 * @param {string} [facetsVals.label] left part of the facet (must be missing if it's an icon)
 * @param {string} facetsVals.value right part of the facet
 */
export function assertSearchFacets(facetsVals = []) {
    const facetEls = document.querySelectorAll(".o_searchview_facet");
    assert(facetEls.length, facetsVals.length, `Expected ${facetsVals.length} search facets.`);
    for (let i = 0; i < facetsVals.length; i++) {
        const facetLabel = facetEls[i].querySelector(".o_searchview_facet_label").innerText;
        const facetValue = facetEls[i].querySelector(".o_facet_values").innerText;
        const { label = "", value } = facetsVals[i];
        assert(facetLabel, label, "Not the expected search facet");
        assert(facetValue, value, `Wrong value for search facet ${label}`);
    }
}

/**
 * Check a specific line (move line, quality step or work order) matches all given data.
 * @param {Object} values
 * @param {Integer} [values.index] line's index, must be used if `step` is not given
 * @param {string} values.label expected line's label
 * @param {string} [values.value] expected line's value, should not be used if line has no value
 * @param {HTMLElement} [values.record] must be given if there is more than one record, optionnal otherwise
 * @param {HTMLElement} [values.step] the check line, must be used if `index` not given
 */
export function assertStep(values) {
    const { index, label, value } = values;
    const recordEl = values.record || getRecord();
    const headerEl = recordEl.querySelector("&>.card-header");
    const moName = headerEl.querySelector(".o_record_name h4").innerText;
    const lineEl = values.step || recordEl.querySelectorAll("&>ul>li")[index];
    const lineLabel = lineEl.querySelector(".o_line_label").innerText;
    const lineQty = lineEl.querySelector(".o_mrp_record_line_qty")?.innerText;
    const lineUom = lineEl.querySelector(".o_mrp_record_line_uom")?.innerText;
    const lineValue = lineQty ? `${lineQty} ${lineUom}` : undefined;
    assert(lineLabel, label, `Wrong label for "${moName}" line`);
    if (value) {
        assert(lineValue, value, `"${moName}" line "${lineLabel}" has wrong value`);
    } else if (lineValue) {
        fail(`"${moName} line "${lineLabel}" should have no value: got "${lineValue}" instead.`);
    }
}

/**
 * Check the Workcenter buttons display the expected Workcenters in the expected
 * order. Also check which one is the active button.
 * @param {Array} buttons list of all displayed Workcenter buttons
 * @param {string} buttons.name expected button's name
 * @param {Number} buttons.count expected button's count
 * @param {Boolean} [buttons.active] must be true only for the expected active button
 */
export function assertWorkcenterButtons(buttons) {
    const buttonEls = document.querySelectorAll(".o_work_center_btn");
    assert(buttonEls.length, buttons.length, "There is more or less WC buttons than expected");

    for (let i = 0; i < buttons.length; i++) {
        const { name, count, active = false } = buttons[i];
        const buttonEl = buttonEls[i];
        const buttonName = buttonEl.firstChild.data;
        const buttonCount = Number(buttonEl.querySelector(".o_tabular_nums").innerText);
        assert(buttonName, name, "Not the right button");
        assert(buttonCount, count, `Not the right count for button "${name}"`);
        const errorMsg = active
            ? `Button "${name}" should be active but is not`
            : `Button "${name}" should not be active but it is`;
        assert(buttonEl.classList.contains("active"), active, errorMsg);
    }
}

/**
 * Check a specific record (manufacturing order or work order) matches all given data.
 * @param {Object} values
 * @param {Integer} [values.index] record's index, must be used if multiple
 * records are visible but optionnal of there is only one record at the time
 * @param {string} values.name expected record's name
 * @param {string} [values.operation] expected record's operation
 * @param {string} values.product expected record product's name
 * @param {string} values.quantity expected record's producted quantity, UoM included
 * @param {Object[]} [values.steps=[]] every record's line, must be given only
 * if record has at least one line. For more information, @see {@link assertStep}
 */
export function assertWorkOrderValues(values) {
    const { name, operation, steps = [] } = values;
    const recordEls = getRecords();
    if (!values.index && recordEls.length > 1) {
        fail("No record's index specified but multiple records found. An index is needed.");
    }
    const recordEl = recordEls[values.index || 0];
    const headerEl = recordEl.querySelector("&>.card-header");
    const linesEl = recordEl.querySelectorAll("&>ul>li");
    // Check record's name (and operation in case of a Work Order.)
    const moName = headerEl.querySelector(".o_record_name h4").innerText;
    const operationName = headerEl.querySelector("h5")?.innerText;
    assert(moName, name, "Wrong record's name");
    if (operation) {
        assert(operationName, operation, `Wrong operation for record "${name}"`);
    } else if (operationName) {
        fail(`Record "${name}" is for the operation "${operation}" but no operation expected`);
    }
    // Check produced product and quantities.
    const product = headerEl.querySelector(".o_finished_product").innerText;
    assert(product, values.product, `Wrong finished product for record "${name}"`);
    const quantity = headerEl.querySelector(".o_quantity").innerText;
    assert(quantity, values.quantity, `Wrong quantity to produce for record "${name}"`);

    // Check every record's line label and value.
    assert(linesEl.length, steps.length, `Record "${name}" should have ${steps.length} line(s)`);
    for (let i = 0; i < steps.length; i++) {
        const { label, value } = steps[i];
        const step = linesEl[i];
        assertStep({ record: recordEl, step, label, value });
    }
}
