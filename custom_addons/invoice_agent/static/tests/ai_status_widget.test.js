/** @odoo-module **/

import { expect, test, animationFrame } from "@odoo/hoot";
import { registry } from "@web/core/registry";
import { mailModels } from "@mail/../tests/mail_test_helpers";
import {
    defineModels,
    fields,
    mockService,
    models,
    mountView,
    mountWithCleanup,
} from "@web/../tests/web_test_helpers";

// ---------------------------------------------------------------------------
// The widget under test is reached through the field registry, exactly like
// the form renderer does it. Importing the source module directly would tie
// the test to its asset path; the registry entry is the contract that
// `widget="ai_status_widget"` resolves against.
// ---------------------------------------------------------------------------

function getAIStatusWidget() {
    const descriptor = registry.category("fields").get("ai_status_widget");
    if (!descriptor) {
        throw new Error(
            "the 'ai_status_widget' field widget is not registered: " +
            "invoice_agent/static/src/js/ai_status_widget.js did not load"
        );
    }
    return descriptor;
}

// ---------------------------------------------------------------------------
// bus_service double
//
// The widget listens to the `invoice_agent` channel, which the server feeds
// over the bus. The real service talks to a SharedWorker, so the test replaces
// only the three subscriptions-related methods and keeps the rest of the real
// service (mail and friends call `addEventListener` on it while starting).
//
// `mockService` is called from the test body: the registry is snapshotted
// before each test, so the double is torn down with it and never leaks into
// another suite.
// ---------------------------------------------------------------------------

const CHANNEL = "invoice_agent";

/** @type {Map<string, Set<Function>>} notification type -> subscribers */
let busSubscriptions = new Map();
/** @type {string[]} channels added to the bus by the widget under test */
let busChannels = [];

function installBusServiceDouble() {
    busSubscriptions = new Map();
    busChannels = [];
    mockService("bus_service", {
        addChannel(channel) {
            busChannels.push(channel);
        },
        subscribe(notificationType, callback) {
            if (!busSubscriptions.has(notificationType)) {
                busSubscriptions.set(notificationType, new Set());
            }
            busSubscriptions.get(notificationType).add(callback);
        },
        unsubscribe(notificationType, callback) {
            busSubscriptions.get(notificationType)?.delete(callback);
        },
    });
}

/**
 * Delivers a notification on the channel the widget listens to.
 *
 * @param {object} payload the notification body, e.g. `{ move_id, status }`
 */
function emitNotification(payload) {
    for (const callback of busSubscriptions.get(CHANNEL) ?? []) {
        callback(payload, { id: 1 });
    }
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

class Move extends models.Model {
    _name = "invoice_agent.test.move";

    ai_job_uuid = fields.Char({ string: "AI Job" });

    _records = [{ id: 1, ai_job_uuid: "job-0001" }];
}

defineModels([Move]);
// Mail ships with `account` (account -> portal -> mail) and its services ask
// the mock server for `discuss.channel` as soon as an env starts. Registering
// `mailModels` directly (rather than through `defineMailModels`, which also
// rewrites the current test suite name) keeps them attached to this suite.
defineModels(mailModels);

/**
 * Builds the field-widget props the form renderer hands to the component.
 *
 * @param {{ resId?: number, aiJobUuid?: string|false }} [options]
 */
function makeRecord({ resId = 1, aiJobUuid = "job-0001" } = {}) {
    return {
        resId,
        data: { ai_job_uuid: aiJobUuid },
    };
}

const AI_JOB_FIELD = "ai_job_uuid";

async function mountWidget(record) {
    installBusServiceDouble();
    // Same props the form renderer hands to a field widget.
    return mountWithCleanup(getAIStatusWidget().component, {
        props: { record, name: AI_JOB_FIELD, readonly: false },
        noMainContainer: true,
    });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test("AIStatusWidget: a bill with an extraction job starts in the queued state", async () => {
    await mountWidget(makeRecord({ aiJobUuid: "job-0001" }));

    expect(".o_ai_status_widget").toHaveText("Queued");
    expect(".o_ai_status_widget").toHaveClass("text-secondary");
    expect(".o_ai_status_widget i").toHaveClass("fa-clock");
});

test("AIStatusWidget: a bill without an extraction job shows a placeholder", async () => {
    await mountWidget(makeRecord({ aiJobUuid: false }));

    expect(".o_ai_status_widget").toHaveText("—");
    expect(".o_ai_status_widget").not.toHaveClass("text-secondary");
    expect(".o_ai_status_widget i").toHaveClass("fa-clock");
});

test("AIStatusWidget: listens on the invoice_agent channel", async () => {
    await mountWidget(makeRecord());

    // Other services (mail, notifications, ...) also use the bus, so only the
    // widget's own subscription is asserted here.
    expect(busChannels.includes(CHANNEL)).toBe(true);
    expect(busSubscriptions.has(CHANNEL)).toBe(true);
});

test("AIStatusWidget: follows the status pushed while the extraction runs", async () => {
    await mountWidget(makeRecord({ resId: 42, aiJobUuid: "job-0042" }));

    emitNotification({ move_id: 42, status: "extracting" });
    await animationFrame();

    expect(".o_ai_status_widget").toHaveText("Extracting…");
    expect(".o_ai_status_widget").toHaveClass("text-info");
    expect(".o_ai_status_widget i").toHaveClass("fa-spin");
});

test("AIStatusWidget: renders the ready state once the extraction is done", async () => {
    await mountWidget(makeRecord({ resId: 42, aiJobUuid: "job-0042" }));

    emitNotification({ move_id: 42, status: "ready" });
    await animationFrame();

    expect(".o_ai_status_widget").toHaveText("Ready");
    expect(".o_ai_status_widget").toHaveClass("text-success");
    expect(".o_ai_status_widget i").toHaveClass("fa-circle-check");
});

test("AIStatusWidget: renders the failed state when the extraction gives up", async () => {
    await mountWidget(makeRecord({ resId: 42, aiJobUuid: "job-0042" }));

    emitNotification({ move_id: 42, status: "failed" });
    await animationFrame();

    expect(".o_ai_status_widget").toHaveText("Failed");
    expect(".o_ai_status_widget").toHaveClass("text-danger");
    expect(".o_ai_status_widget i").toHaveClass("fa-circle-xmark");
});

test("AIStatusWidget: ignores notifications addressed to another bill", async () => {
    await mountWidget(makeRecord({ resId: 42, aiJobUuid: "job-0042" }));

    emitNotification({ move_id: 43, status: "ready" });
    await animationFrame();

    expect(".o_ai_status_widget").toHaveText("Queued");
    expect(".o_ai_status_widget").toHaveClass("text-secondary");
});

test("AIStatusWidget: ignores a status it does not know", async () => {
    await mountWidget(makeRecord({ resId: 42, aiJobUuid: "job-0042" }));

    emitNotification({ move_id: 42, status: "exploded" });
    await animationFrame();

    expect(".o_ai_status_widget").toHaveText("Queued");
});

test("AIStatusWidget: ignores notifications for an unsaved bill", async () => {
    await mountWidget(makeRecord({ resId: undefined, aiJobUuid: "job-0042" }));

    emitNotification({ move_id: undefined, status: "ready" });
    await animationFrame();

    expect(".o_ai_status_widget").toHaveText("Queued");
});

test("AIStatusWidget: is exposed as a char field widget", async () => {
    const descriptor = getAIStatusWidget();

    expect(descriptor.supportedTypes).toEqual(["char"]);
});

test("AIStatusWidget: renders inside a form bound to ai_job_uuid", async () => {
    installBusServiceDouble();

    await mountView({
        type: "form",
        resModel: "invoice_agent.test.move",
        resId: 1,
        arch: /* xml */ `
            <form>
                <field name="ai_job_uuid" widget="ai_status_widget"/>
            </form>
        `,
    });

    expect(".o_field_widget[name=ai_job_uuid] .o_ai_status_widget").toHaveText("Queued");
});
