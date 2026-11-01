/** @odoo-module **/

import { expect, test, animationFrame, Deferred, queryAll, waitUntil } from "@odoo/hoot";
import { click, mailModels } from "@mail/../tests/mail_test_helpers";
import { registry } from "@web/core/registry";
import { defineModels, mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";

// Mail ships with `account` (account -> portal -> mail) and its services ask
// the mock server for `discuss.channel` as soon as an env starts — which
// mounting this widget does. Registering `mailModels` directly (rather than
// through `defineMailModels`, which also rewrites the current test suite name)
// keeps them attached to this suite.
defineModels(mailModels);

// ---------------------------------------------------------------------------
// The panel is reached through the field registry, i.e. exactly how the form
// renderer resolves `widget="invoice_suggestion_panel"`. This also checks that
// invoice_agent/static/src/js/suggestion_panel.js is part of the bundle.
// ---------------------------------------------------------------------------

const FIELD_NAME = "extraction_line_ids";
const RES_ID = 7;
const RES_MODEL = "invoice_agent.test.move";
const APPLY_METHOD = "apply_suggested_value";

function getSuggestionPanel() {
    const descriptor = registry.category("fields").get("invoice_suggestion_panel");
    if (!descriptor) {
        throw new Error(
            "the 'invoice_suggestion_panel' field widget is not registered: " +
            "invoice_agent/static/src/js/suggestion_panel.js did not load"
        );
    }
    return descriptor;
}

// ---------------------------------------------------------------------------
// Fixtures
//
// `record` mimics the shape the one2many field hands to the widget: the value
// of the bound field is a `{ records: [...] }` collection whose entries expose
// their values through `.data`.
// ---------------------------------------------------------------------------

function makeSuggestion(id, fieldName, extractedValue, confidence = 0.9) {
    return {
        id,
        data: {
            field_name: fieldName,
            extracted_value: extractedValue,
            field_confidence: confidence,
        },
    };
}

function makeRecord(suggestions) {
    return {
        resId: RES_ID,
        model: RES_MODEL,
        data: {
            [FIELD_NAME]: { records: suggestions },
        },
        loadCount: 0,
        load() {
            this.loadCount++;
            return Promise.resolve();
        },
    };
}

const REF = makeSuggestion(11, "ref", "INV/2024/001", 0.98);
const INVOICE_DATE = makeSuggestion(12, "invoice_date", "2024-01-15", 0.91);
const PARTNER = makeSuggestion(13, "partner_id", "ACME Corp", 0.42);

/**
 * @param {object} record
 * @param {{ readonly?: boolean }} [options]
 */
async function mountPanel(record, { readonly = false, name = FIELD_NAME } = {}) {
    // Same props the form renderer hands to a field widget.
    return mountWithCleanup(getSuggestionPanel().component, {
        props: { record, name, readonly },
        noMainContainer: true,
    });
}

/**
 * Waits until the panel renders exactly `count` chips.
 *
 * Accepting/rejecting is asynchronous: the click only starts the handler, and
 * the chip disappears once the handler's promise resolves and Owl re-renders.
 * A bare `expect` does not retry, so the assertion has to wait explicitly.
 */
function waitForChips(count) {
    return waitUntil(() => queryAll(".o_invoice_suggestion_chip").length === count);
}

/**
 * Makes `apply_suggested_value` answer with the given value (or with a
 * promise, to hold the call in flight) and records every call it receives.
 */
function mockApply(handler = () => true) {
    const calls = [];
    onRpc(RES_MODEL, APPLY_METHOD, (params) => {
        calls.push({ args: params.args, kwargs: params.kwargs });
        return handler();
    });
    return calls;
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

test("InvoiceSuggestionPanel: renders one chip per extracted field", async () => {
    await mountPanel(makeRecord([REF, INVOICE_DATE, PARTNER]));

    expect(".o_invoice_suggestion_chip").toHaveCount(3);
    expect(".o_invoice_suggestion_chip:eq(0) .fw-semibold").toHaveText("ref");
    expect(".o_invoice_suggestion_chip:eq(0) .text-truncate").toHaveText("INV/2024/001");
    expect(".o_invoice_suggestion_chip:eq(1) .fw-semibold").toHaveText("invoice date");
    expect(".o_invoice_suggestion_chip:eq(1) .text-truncate").toHaveText("2024-01-15");
    expect(".o_invoice_suggestion_chip:eq(2) .fw-semibold").toHaveText("partner id");
});

test("InvoiceSuggestionPanel: a suggestion without a value is shown as a dash", async () => {
    await mountPanel(makeRecord([makeSuggestion(11, "ref", "")]));

    expect(".o_invoice_suggestion_chip .text-truncate").toHaveText("—");
});

test("InvoiceSuggestionPanel: explains how to get suggestions when there is none", async () => {
    await mountPanel(makeRecord([]));

    expect(".o_invoice_suggestion_chip").toHaveCount(0);
    expect(".o_invoice_suggestion_panel > .text-muted").toHaveCount(1);
    expect(".o_invoice_suggestion_panel > .text-muted b").toHaveText("Suggest with AI");
});

test("InvoiceSuggestionPanel: reads the suggestions of the bound field only", async () => {
    const record = makeRecord([REF]);
    record.data.other_field = { records: [INVOICE_DATE] };
    await mountPanel(record);

    expect(".o_invoice_suggestion_chip").toHaveCount(1);
    expect(".o_invoice_suggestion_chip .fw-semibold").toHaveText("ref");
});

test("InvoiceSuggestionPanel: tolerates a record without the bound field", async () => {
    const record = makeRecord([REF]);
    delete record.data[FIELD_NAME];
    await mountPanel(record);

    expect(".o_invoice_suggestion_chip").toHaveCount(0);
    expect(".o_invoice_suggestion_panel > .text-muted").toHaveCount(1);
});

test("InvoiceSuggestionPanel: is exposed as a one2many field widget with its related fields", async () => {
    const descriptor = getSuggestionPanel();

    expect(descriptor.supportedTypes).toEqual(["one2many"]);
    expect(descriptor.relatedFields).toEqual([
        { name: "field_name", type: "char" },
        { name: "extracted_value", type: "text" },
        { name: "field_confidence", type: "float" },
    ]);
});

// ---------------------------------------------------------------------------
// Accepting
// ---------------------------------------------------------------------------

test("InvoiceSuggestionPanel: accepting a chip applies exactly that one field", async () => {
    const calls = mockApply();
    const record = makeRecord([REF, INVOICE_DATE]);
    await mountPanel(record);

    await click(".o_invoice_suggestion_chip:eq(0) button.btn-success");

    await waitForChips(1);
    expect(".o_invoice_suggestion_chip:eq(0) .fw-semibold").toHaveText("invoice date");
    expect(calls.length).toBe(1);
    expect(calls[0].args).toEqual([RES_ID]);
    expect(calls[0].kwargs.field_name).toBe("ref");
    expect(record.loadCount).toBe(1);
});

test("InvoiceSuggestionPanel: a chip offers the value it will apply as tooltip", async () => {
    await mountPanel(makeRecord([REF]));

    expect(".o_invoice_suggestion_chip button.btn-success").toHaveAttribute(
        "title",
        "Apply INV/2024/001"
    );
    expect(".o_invoice_suggestion_chip button.btn-danger").toHaveAttribute("title", "Reject ref");
});

test("InvoiceSuggestionPanel: only one call is sent per field while it is in flight", async () => {
    let callCount = 0;
    const deferred = new Deferred();
    onRpc(RES_MODEL, APPLY_METHOD, () => {
        callCount++;
        return deferred;
    });

    const panel = await mountPanel(makeRecord([REF]));
    const [suggestion] = panel.suggestions;

    const firstCall = panel.acceptSuggestion(suggestion);
    const secondCall = panel.acceptSuggestion(suggestion);

    // The second call is refused straight away: the field is already in flight.
    expect(Boolean(panel.state.applying["ref"])).toBe(true);
    await animationFrame();

    deferred.resolve(true);
    await Promise.all([firstCall, secondCall]);

    expect(callCount).toBe(1);
    expect(Boolean(panel.state.spent["ref"])).toBe(true);
});

test("InvoiceSuggestionPanel: shows progress and locks the chips while a call is in flight", async () => {
    const deferred = new Deferred();
    onRpc(RES_MODEL, APPLY_METHOD, () => deferred);
    await mountPanel(makeRecord([REF, INVOICE_DATE]));

    await click(".o_invoice_suggestion_chip:eq(0) button.btn-success");

    await waitUntil(
        () => queryAll(".o_invoice_suggestion_panel > .text-muted > .fa-spin").length === 1
    );
    expect(".o_invoice_suggestion_chip:eq(0) button.btn-success").toHaveAttribute("disabled");
    expect(".o_invoice_suggestion_chip:eq(0) button.btn-danger").toHaveAttribute("disabled");
    expect(".o_invoice_suggestion_chip:eq(1) button.btn-success").toHaveAttribute("disabled");

    deferred.resolve(true);

    await waitForChips(1);
    expect(".o_invoice_suggestion_panel > .text-muted > .fa-spin").toHaveCount(0);
});

test("InvoiceSuggestionPanel: a failed application keeps the chip for a retry", async () => {
    mockApply(() => {
        throw new Error("Vendor not found");
    });
    const panel = await mountPanel(makeRecord([PARTNER]));
    const [suggestion] = panel.suggestions;

    let rejection = null;
    try {
        await panel.acceptSuggestion(suggestion);
    } catch (error) {
        rejection = error;
    }

    expect(rejection).not.toBe(null);
    expect(".o_invoice_suggestion_chip").toHaveCount(1);
    expect(Boolean(panel.state.spent["partner_id"])).toBe(false);
});

// ---------------------------------------------------------------------------
// Rejecting
// ---------------------------------------------------------------------------

test("InvoiceSuggestionPanel: rejecting a chip is local and does not reload the bill", async () => {
    const calls = mockApply();
    const record = makeRecord([REF, INVOICE_DATE]);
    await mountPanel(record);

    await click(".o_invoice_suggestion_chip:eq(0) button.btn-danger");

    await waitForChips(1);
    expect(".o_invoice_suggestion_chip:eq(0) .fw-semibold").toHaveText("invoice date");
    expect(calls).toEqual([]);
    expect(record.loadCount).toBe(0);
});

test("InvoiceSuggestionPanel: a rejected field stays rejected until the bill is reloaded", async () => {
    const panel = await mountPanel(makeRecord([REF, INVOICE_DATE]));

    await click(".o_invoice_suggestion_chip:eq(0) button.btn-danger");
    await waitForChips(1);

    expect(Boolean(panel.state.spent["ref"])).toBe(true);
    expect(panel.suggestions.map((suggestion) => suggestion.data.field_name)).toEqual([
        "invoice_date",
    ]);
});

// ---------------------------------------------------------------------------
// Readonly
// ---------------------------------------------------------------------------

test("InvoiceSuggestionPanel: a readonly panel cannot be acted upon", async () => {
    await mountPanel(makeRecord([REF, INVOICE_DATE]), { readonly: true });

    expect(".o_invoice_suggestion_chip").toHaveCount(2);
    expect(".o_invoice_suggestion_chip button.btn-success").toHaveAttribute("disabled");
    expect(".o_invoice_suggestion_chip button.btn-danger").toHaveAttribute("disabled");
});
