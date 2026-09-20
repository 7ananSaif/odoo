import { describe, expect, test } from "@odoo/hoot";
import { click } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { mountWithCleanup, defineModels } from "@web/../tests/web_test_helpers";
import { mailModels } from "@mail/../tests/mail_test_helpers";

import { BankRecButton } from "@account_accountant/components/bank_reconciliation/button/button";

// Due to dependency with mail module, we have to define their models for our tests.
defineModels(mailModels);

describe.current.tags("desktop");

test("can display a button", async () => {
    await mountWithCleanup(BankRecButton, {
        props: {
            label: "A label",
            action: () => {},
            count: null,
            primary: false,
        },
    });

    expect(".btn.btn-secondary").toHaveText("A label");
});

test("can display a button with a count", async () => {
    await mountWithCleanup(BankRecButton, {
        props: {
            label: "Another label",
            action: () => {},
            count: 10,
            primary: false,
        },
    });

    expect(".btn span:first").toHaveText("Another label");
    expect(".btn span:last").toHaveText("10");
});

test("can display a button with primary class", async () => {
    await mountWithCleanup(BankRecButton, {
        props: {
            label: "A label with primary class",
            action: () => {},
            count: null,
            primary: true,
        },
    });

    expect(".btn.btn-primary").toHaveText("A label with primary class");
});

test("can call function when button is clicked", async () => {
    let counter = 0;

    await mountWithCleanup(BankRecButton, {
        props: {
            label: "A button with an action",
            action: () => counter++,
            count: null,
            primary: false,
        },
    });

    await click(".btn");
    await animationFrame();
    expect(counter).toBe(1);
});
