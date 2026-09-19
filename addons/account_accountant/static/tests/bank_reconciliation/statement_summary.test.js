import { describe, expect, test } from "@odoo/hoot";
import { click, queryOne } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { mountWithCleanup, defineModels } from "@web/../tests/web_test_helpers";
import { mailModels } from "@mail/../tests/mail_test_helpers";

import { BankRecStatementSummary } from "@account_accountant/components/bank_reconciliation/statement_summary/statement_summary";

// Due to dependency with mail module, we have to define their models for our tests.
defineModels(mailModels);

describe.current.tags("desktop");

test("can display a BankRecStatementSummary", async () => {
    let counter = 0;
    await mountWithCleanup(BankRecStatementSummary, {
        props: {
            label: "A label",
            action: () => {
                counter++;
            },
            amount: "$1,000.00",
        },
    });
    const elements = queryOne("div.o_statement_summary").children;
    await click(elements[2]);
    await animationFrame();
    expect(counter).toBe(1);
    expect(elements[0]).toHaveText("A label");
    expect(elements[2]).toHaveText("$1,000.00");
});

test("no amount displayed if no amount in props", async () => {
    await mountWithCleanup(BankRecStatementSummary, {
        props: {
            label: "A label",
            action: () => {},
        },
    });
    const elements = queryOne("div.o_statement_summary").children;
    expect(elements).toHaveCount(2);
});

test("label in text danger when isValid set to False", async () => {
    await mountWithCleanup(BankRecStatementSummary, {
        props: {
            label: "A label",
            isValid: false,
            action: () => {},
            amount: "$1,000.00",
        },
    });
    expect("div.o_statement_summary > div > h4").toHaveClass("text-danger");
});
