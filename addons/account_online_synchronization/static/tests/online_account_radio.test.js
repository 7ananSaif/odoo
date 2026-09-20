import { defineAccountOnlineSynchronizationModels } from "./acount_online_synchronization_test_helpers";
import { test } from "@odoo/hoot";
import {
    click,
    contains,
    openFormView,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { onRpc } from "@web/../tests/web_test_helpers";

defineAccountOnlineSynchronizationModels();

test("can be rendered", async () => {
    const pyEnv = await startServer();
    const onlineLink = pyEnv["account.online.link"].create({
        state: "connected",
        name: "Fake Bank",
    });
    pyEnv["account.online.account"].create([
        {
            name: "account_1",
            online_identifier: "abcd",
            balance: 10.0,
            account_number: "account_number_1",
            account_online_link_id: onlineLink,
        },
        {
            name: "account_2",
            online_identifier: "efgh",
            balance: 20.0,
            account_number: "account_number_2",
            account_online_link_id: onlineLink,
        },
    ]);
    const bankSelection = pyEnv["account.bank.selection"].create({
        account_online_link_id: onlineLink,
    });
    onRpc(({ method, model }) => {
        if (model === "account.online.account" && method === "get_formatted_balances") {
            return {
                1: ["$ 10.0", 10.0],
                2: ["$ 20.0", 20.0],
            };
        }
    });
    await start();
    await openFormView("account.bank.selection", bankSelection, {
        arch: `
        <form>
            <div>
                <field name="account_online_account_ids" invisible="1"/>
                <field name="selected_account" widget="online_account_radio" nolabel="1"/>
            </div>
        </form>`,
    });
    await contains(".o_radio_item", { count: 2 });
    await contains(":nth-child(1 of .o_radio_item)", {
        contains: [
            ["p", { text: "$ 10.0" }],
            ["label", { text: "account_1" }],
            [".o_radio_input:checked"],
        ],
    });
    await contains(":nth-child(2 of .o_radio_item)", {
        contains: [
            ["p", { text: "$ 20.0" }],
            ["label", { text: "account_2" }],
            [".o_radio_input:not(:checked)"],
        ],
    });
    await click(":nth-child(2 of .o_radio_item) .o_radio_input");
    await contains(":nth-child(1 of .o_radio_item) .o_radio_input:not(:checked)");
    await contains(":nth-child(2 of .o_radio_item) .o_radio_input:checked");
});
