import { mailModels } from "@mail/../tests/mail_test_helpers";
import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { click, queryAll, queryAllTexts, queryOne } from "@odoo/hoot-dom";
import { animationFrame, mockDate } from "@odoo/hoot-mock";
import {
    contains,
    defineModels,
    fields,
    getService,
    models,
    mountWithCleanup,
} from "@web/../tests/web_test_helpers";
import { WebClient } from "@web/webclient/webclient";

import { BankRecSelectCreateDialog } from "@account_accountant/components/bank_reconciliation/search_dialog/search_dialog";

class AccountMoveLine extends models.Model {
    name = fields.Char({ string: "Name" });
    date = fields.Date({ string: "Date" });
    partner_id = fields.Many2one({ string: "Partner", relation: "partner" });
    amount_residual = fields.Float({ string: "Amount Residual" });

    amount_residual_currency = fields.Float({ string: "Amount Residual Currency" });

    currency_id = fields.Many2one({ string: "Currency", relation: "res.currency" });

    company_currency_id = fields.Many2one({ string: "Currency", relation: "res.currency" });

    _records = [
        {
            id: 1,
            name: "INV/2025/0001",
            date: "2025-01-11",
            partner_id: 1,
            amount_residual: -230,
            currency_id: 1,
        },
        {
            id: 2,
            name: "INV/2025/0002",
            date: "2025-01-12",
            partner_id: 1,
            amount_residual: -150,
            currency_id: 1,
        },
        {
            id: 3,
            name: "INV/2025/0003",
            date: "2025-01-13",
            partner_id: 1,
            amount_residual: -50,
            currency_id: 1,
        },
        {
            id: 4,
            name: "INV/2025/0004",
            date: "2025-01-14",
            partner_id: 2,
            amount_residual: -100,
            currency_id: 1,
        },
        {
            id: 5,
            name: "INV/2025/0005",
            date: "2025-01-15",
            partner_id: 3,
            amount_residual: -125,
            currency_id: 1,
        },
    ];

    _views = {
        list: /* xml */ `
            <list js_class="bank_rec_dialog_list" string="Account Move Line">
                <field name="date"/>
                <field name="name"/>
                <field name="partner_id"/>
                <field name="amount_residual"/>
                <field name="amount_residual_currency"/>
                <field name="currency_id"/>
            </list>
        `,
        search: /* xml */ `
            <search>
                <field name="partner_id"/>
            </search>
        `,
        kanban: /* xml */ `
            <kanban>
                <field name="date"/>
                <field name="name"/>
                <templates>
                    <t t-name="card"/>
                </templates>
            </kanban>
        `,
        form: /* xml */ `
            <form/>
        `,
    };
}

class Partner extends models.Model {
    name = fields.Char({ string: "Name" });

    _records = [
        { id: 1, name: "Jean Pierre" },
        { id: 2, name: "Pierre Jean" },
        { id: 3, name: "JB Pokie" },
    ];
}

// Due to dependency with mail module, we have to define their models for our tests.
defineModels({ ...mailModels, AccountMoveLine, Partner });

beforeEach(() => {
    mockDate("2025-04-22 00:00:00");
});

describe.current.tags("desktop");

test("BankRecSelectCreateDialog footer with right information", async () => {
    await mountWithCleanup(WebClient);
    getService("dialog").add(BankRecSelectCreateDialog, {
        noCreate: true,
        resModel: "account.move.line",
        suspenseAccountLine: {
            amount_currency: 233.33,
            currency_id: { id: 1 },
            company_currency_id: { id: 1 },
        },
        date: luxon.DateTime.now(),
        reference: "A cool reference to display",
        context: { search_default_partner_id: 1 },
        domain: [],
    });
    await animationFrame();

    const bankReconciliationInfoNode = queryOne("div[name='bank_reconciliation_info']").children;
    const bankReconciliationInfo = queryAllTexts(bankReconciliationInfoNode);
    expect(bankReconciliationInfo[0]).toBe("4/22/2025");
    expect(bankReconciliationInfo[1]).toBe("A cool reference to display");
    expect(bankReconciliationInfo[2]).toBe("Balance: $ 233.33");
});

test("BankRecSelectCreateDialog list view single currency", async () => {
    await mountWithCleanup(WebClient);
    getService("dialog").add(BankRecSelectCreateDialog, {
        noCreate: true,
        resModel: "account.move.line",
        suspenseAccountLine: {
            amount_currency: 100,
            currency_id: { id: 1 },
            company_currency_id: { id: 1 },
        },
        reference: "A useless reference",
        date: luxon.DateTime.now(),
        context: { search_default_partner_id: 1 },
        domain: [],
    });
    await animationFrame();

    expect("div[name='remaining_amount']").toHaveText("Balance: $ 100.00");
    expect("div.o_facet_values > small.o_facet_value").toHaveText("Jean Pierre");
    // Check that we have 4 checkboxes (Select all + 3 elements)
    let checkboxes = queryAll(".form-check > .form-check-input[type='checkbox']");
    expect(checkboxes.length).toBe(4);
    // Select an element already fetch
    await click(checkboxes[2]);
    await animationFrame();
    // Unselect this element
    await click(checkboxes[2]);
    await animationFrame();

    await click("div.o_facet_values > button.o_facet_remove");
    await animationFrame();
    // Check that we have 6 checkboxes (Select all + 5 elements)
    checkboxes = queryAll(".form-check > .form-check-input[type='checkbox']");
    expect(checkboxes.length).toBe(6);

    await click(checkboxes[4]);
    await animationFrame();
    await animationFrame();
    // Check that the balance is correctly affected by the selection
    expect("div[name='remaining_amount']").toHaveText("Balance: $ 0.00");

    await click(checkboxes[4]);
    await animationFrame();
    await animationFrame();
    expect("div[name='remaining_amount']").toHaveText("Balance: $ 100.00");

    await click(".o_pager_value");
    await animationFrame();
    expect(".o_pager_counter .o_pager_value").toHaveValue("1-5");

    await contains("input.o_pager_value").edit("1-2");
    await click(document.body);
    await animationFrame();

    checkboxes = queryAll(".form-check > .form-check-input[type='checkbox']");
    expect(checkboxes.length).toBe(3);
    await click(checkboxes[0]);
    await animationFrame();

    await contains(`.o_select_domain`).click();
    await animationFrame();

    expect("div[name='remaining_amount']").toHaveText("Balance: $ -555.00");
});

test("BankRecSelectCreateDialog list view multi currencies", async () => {
    AccountMoveLine._records.push({
        id: 6,
        name: "INV/2025/0006",
        date: "2025-01-15",
        partner_id: 3,
        amount_residual: -100,
        amount_residual_currency: -200,
        currency_id: 2,
    });
    AccountMoveLine._records.push({
        id: 7,
        name: "INV/2025/0007",
        date: "2025-01-15",
        partner_id: 3,
        amount_residual: -100,
        amount_residual_currency: -100,
        currency_id: 1,
    });
    await mountWithCleanup(WebClient);
    getService("dialog").add(BankRecSelectCreateDialog, {
        noCreate: true,
        resModel: "account.move.line",
        suspenseAccountLine: {
            amount_currency: 100,
            currency_id: { id: 2 },
            company_currency_id: { id: 1 },
        },
        reference: "A useless reference",
        date: luxon.DateTime.now(),
        context: { search_default_partner_id: 3 },
        domain: [],
    });
    await animationFrame();
    expect("div[name='remaining_amount']").toHaveText("Balance: 100.00 €");

    const checkboxes = queryAll(".form-check > .form-check-input[type='checkbox']");
    expect(checkboxes.length).toBe(4);

    await click(checkboxes[2]);
    await animationFrame();
    await animationFrame();
    expect("div[name='remaining_amount']").toHaveText("Balance: -100.00 €");

    await click(checkboxes[2]);
    await animationFrame();
    await animationFrame();
    expect("div[name='remaining_amount']").toHaveText("Balance: 100.00 €");

    // Different currencies cannot be computed together
    await click(checkboxes[3]);
    await animationFrame();
    await animationFrame();
    expect("div[name='remaining_amount']").toHaveText("Balance: /");
});
