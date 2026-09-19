import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { Deferred, edit } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import {
    contains,
    defineModels,
    fields,
    getService,
    models,
    mountView,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { user } from "@web/core/user";
import { WebClientEnterprise } from "@web_enterprise/webclient/webclient";

describe.current.tags("desktop");

defineMailModels();

class Partner extends models.Model {
    _name = "partner";

    int_field = fields.Integer({ string: "int_field" });
    bar = fields.Boolean();

    _records = [
        {
            display_name: "first record",
            int_field: 42,
            bar: true,
        },
        {
            display_name: "second record",
            int_field: 27,
            bar: true,
        },
        {
            display_name: "another record",
            int_field: 21,
            bar: false,
        },
    ];

    _views = {
        form: `
        <form>
            <button type="object=" name="someMethod" string="Apply Method"/>
        </form>`,
        list: `<list><field name="display_name"/></list>`,
    };

    get_views() {
        const result = super.get_views(...arguments);
        for (const modelInfo of Object.values(result.models)) {
            modelInfo.has_approval_rules = true;
        }
        return result;
    }
}

defineModels([Partner]);

const defaultRules = {
    1: {
        id: 1,
        approval_group_id: [1, "Internal User"],
        domain: false,
        can_validate: true,
        message: false,
        exclusive_user: false,
    },
};

test("approval components are synchronous", async () => {
    const def = new Deferred();

    onRpc("get_approval_spec", async () => {
        expect.step("get_approval_spec");
        await def;
        return {
            all_rules: defaultRules,
            partner: [[[false, "myMethod", false], { rules: [1], entries: [] }]],
        };
    });

    await mountView({
        resModel: "partner",
        type: "form",
        arch: `<form><button type="object" name="myMethod"/></form>`,
    });

    expect.verifySteps(["get_approval_spec"]);
    expect("button .o_web_studio_approval .fa-circle-o-notch.fa-spin").toHaveCount(1);
    def.resolve();
    await animationFrame();
    expect("button .o_web_studio_approval .fa-circle-o-notch.fa-spin").toHaveCount(0);
    expect("button .o_web_studio_approval .o_web_studio_approval_avatar").toHaveCount(1);
});

test("approval widget basic rendering", async () => {
    onRpc("get_approval_spec", () => {
        expect.step("get_approval_spec");
        return {
            all_rules: defaultRules,
            partner: [
                [[2, "someMethod", false], { rules: [1], entries: [] }],
                [[2, "anotherMethod", false], { rules: [1], entries: [] }],
            ],
        };
    });

    await mountView({
        resModel: "partner",
        type: "form",
        resId: 2,
        arch: `
        <form string="Partners">
            <sheet>
                <header>
                    <button type="object" name="someMethod" string="Apply Method"/>
                </header>
                <div name="button_box">
                    <button class="oe_stat_button" name="yetAnotherMethod" id="visibleStat">
                        <field name="int_field"/>
                    </button>
                    <button class="oe_stat_button"
                            invisible="bar" id="invisibleStat"
                            name="yetAnotherMethod">
                        <field name="bar"/>
                    </button>
                </div>
                <group>
                    <group style="background-color: red">
                        <field name="display_name"/>
                        <field name="bar"/>
                        <field name="int_field"/>
                    </group>
                </group>
                <button type="object" name="anotherMethod"
                        string="Apply Second Method"/>
            </sheet>
        </form>`,
    });

    expect("button[name='someMethod'] .o_web_studio_approval").toHaveCount(1);
    expect("#visibleStat .o_web_studio_approval").toHaveCount(1);
    expect("button[name='anotherMethod'] .o_web_studio_approval").toHaveCount(1);
    expect("#invisibleStat .o_web_studio_approval").toHaveCount(0);
    expect(".o_group .o_web_studio_approval").toHaveCount(0);
    expect.verifySteps(["get_approval_spec"]);

    await contains("button[name='someMethod'] .o_web_studio_approval").click();
    expect(".o-approval-popover").toHaveCount(1);

    expect(".o-approval-popover .o_web_studio_approval_no_entry").toHaveCount(1);
    expect(".o-approval-popover .o_web_approval_approve").toHaveCount(1);
    expect(".o-approval-popover .o_web_approval_reject").toHaveCount(1);
    expect(".o-approval-popover .o_web_approval_cancel").toHaveCount(0);
});

test("approval check: method button", async () => {
    onRpc("get_approval_spec", () => {
        expect.step("get_approval_spec");
        return {
            all_rules: defaultRules,
            partner: [[[2, "someMethod", false], { rules: [1], entries: [] }]],
        };
    });

    onRpc("check_approval", () => {
        /* the check_approval should not be
        called for method buttons, as the validation
        check is done in the backend side. if this
        code is traversed, the test *must* fail!
        that's why it's not included in the expected count
        or in the verifySteps call */
        expect.step("should_not_happen!");
    });

    onRpc("someMethod", () => {
        expect.step("someMethod");
        return true;
    });

    await mountView({
        resModel: "partner",
        type: "form",
        resId: 2,
        arch: `
        <form string="Partners">
            <sheet>
                <header>
                    <button type="object" id="mainButton" name="someMethod"
                                string="Apply Method"/>
                </header>
                <group>
                    <group style="background-color: red">
                        <field name="display_name"/>
                        <field name="bar"/>
                        <field name="int_field"/>
                    </group>
                </group>
            </sheet>
        </form>`,
    });

    await contains("#mainButton").click();
    expect.verifySteps(["get_approval_spec", "someMethod", "get_approval_spec"]);
});

test("approval check: action button", async () => {
    onRpc("get_approval_spec", () => {
        expect.step("get_approval_spec");
        return {
            all_rules: defaultRules,
            partner: [[[2, false, "someaction"], { rules: [1], entries: [] }]],
        };
    });

    onRpc("check_approval", () => {
        expect.step("attempt_action");
        return {
            approved: false,
            rules: [defaultRules[1]],
            entries: [],
        };
    });

    await mountView({
        resModel: "partner",
        type: "form",
        resId: 2,
        arch: `
        <form string="Partners">
            <sheet>
                <header>
                    <button id="mainButton" class="oe_stat_button" type="action" name="someaction">
                        Test
                    </button>
                </header>
                <group>
                    <group style="background-color: red">
                        <field name="display_name"/>
                        <field name="bar"/>
                        <field name="int_field"/>
                    </group>
                </group>
            </sheet>
        </form>`,
    });

    await contains("#mainButton").click();
    expect.verifySteps(["get_approval_spec", "attempt_action", "get_approval_spec"]);
});

test("approval check: rpc is batched", async () => {
    onRpc("get_approval_spec", () => {
        expect.step("get_approval_spec");
        return {
            all_rules: defaultRules,
            partner: [
                [[2, "someMethod", false], { rules: [1], entries: [] }],
                [[2, "someMethod2", false], { rules: [1], entries: [] }],
            ],
        };
    });

    await mountView({
        resModel: "partner",
        type: "form",
        resId: 2,
        arch: `
        <form string="Partners">
            <sheet>
                <header>
                    <button type="object" id="mainButton" name="someMethod"
                                string="Apply Method"/>
                    <button type="object" id="mainButton" name="someMethod2"
                                string="Apply Method 2"/>
                </header>
                <group>
                    <group style="background-color: red">
                        <field name="display_name"/>
                        <field name="bar"/>
                        <field name="int_field"/>
                    </group>
                </group>
            </sheet>
        </form>`,
    });

    expect.verifySteps(["get_approval_spec"]);
});

test("approval widget basic flow", async () => {
    patchWithCleanup(user, {
        userId: 42,
    });

    let hasValidatedRule;

    onRpc("get_approval_spec", () => {
        const entries = [];
        if (hasValidatedRule !== undefined) {
            entries.push({
                id: 1,
                approved: hasValidatedRule,
                user_id: [42, "Some rando"],
                write_date: "2020-04-07 12:43:48",
                rule_id: [1, "someMethod/partner (Internal User)"],
                model: "partner",
                res_id: 2,
            });
        }
        return {
            all_rules: defaultRules,
            partner: [[[2, "someMethod", false], { rules: [1], entries }]],
        };
    });

    onRpc("set_approval", ({ kwargs }) => {
        hasValidatedRule = kwargs.approved;
        expect.step(hasValidatedRule ? "approve_rule" : "reject_rule");
        return true;
    });

    onRpc("delete_approval", () => {
        hasValidatedRule = undefined;
        expect.step("delete_approval");
        return true;
    });

    await mountView({
        resModel: "partner",
        type: "form",
        resId: 2,
        arch: `
        <form string="Partners">
            <sheet>
                <header>
                    <button type="object=" name="someMethod" string="Apply Method"/>
                </header>
                <group>
                    <group style="background-color: red">
                        <field name="display_name"/>
                        <field name="bar"/>
                        <field name="int_field"/>
                    </group>
                </group>
            </sheet>
        </form>`,
    });

    await contains("button[name='someMethod'] .o_web_studio_approval").click();
    expect(".o_popover").toHaveCount(1);
    await contains(".o_popover button.o_web_approval_approve").click();
    await contains(".o_popover button.o_web_approval_cancel").click();
    await contains(".o_popover button.o_web_approval_reject").click();
    expect.verifySteps(["approve_rule", "delete_approval", "reject_rule"]);
});

test("approval widget basic flow with domain rule", async () => {
    expect.assertions(3);

    let index = 0;
    const recordIds = [1, 2, 3];

    onRpc("get_approval_spec", ({ args }) => {
        const currentIndex = index++;
        defaultRules[currentIndex] = { ...defaultRules[1], id: currentIndex };
        expect(recordIds[currentIndex]).toEqual(args[0][0].res_id);
        return {
            all_rules: defaultRules,
            partner: [
                [[args[0][0].res_id, "someMethod", false], { rules: [currentIndex], entries: [] }],
            ],
        };
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await getService("action").doAction({
        name: "Partner",
        res_model: "partner",
        type: "ir.actions.act_window",
        views: [
            [false, "list"],
            [false, "form"],
        ],
    });

    await contains(".o_data_row .o_data_cell").click();
    await contains(".o_pager_next").click();
    await contains("button[name='someMethod'] .o_web_studio_approval").click();
    await contains(".o_pager_next").click();
    await contains("button[name='someMethod'] .o_web_studio_approval").click();
});

test("approval on new record: save before check", async () => {
    onRpc("get_approval_spec", ({ args }) => {
        expect.step(`get_approval_spec: ${JSON.stringify(args)}`);
        return {
            all_rules: defaultRules,
            partner: [[[args[0][0].res_id, false, "someMethod"], { rules: [1], entries: [] }]],
        };
    });

    onRpc("web_save", () => {
        expect.step("web_save");
    });

    onRpc("check_approval", ({ args }) => {
        expect.step(`check_approval: ${JSON.stringify(args)}`);
        return {
            approved: false,
            rules: [
                {
                    id: 1,
                    group_id: [1, "Internal User"],
                    domain: false,
                    can_validate: true,
                    message: false,
                    exclusive_user: false,
                },
            ],
            entries: [],
        };
    });

    await mountView({
        resModel: "partner",
        type: "form",
        arch: `
        <form>
            <button type="action" name="someMethod" string="Apply Method"/>
        </form>`,
    });

    expect.verifySteps([
        'get_approval_spec: [[{"model":"partner","method":false,"action_id":"someMethod","res_id":false}]]',
    ]);
    await contains("button[name='someMethod']").click();
    expect.verifySteps([
        "web_save",
        'check_approval: ["partner",4,false,"someMethod"]',
        'get_approval_spec: [[{"model":"partner","method":false,"action_id":"someMethod","res_id":4}]]',
    ]);
});

test("approval on existing record: save before check", async () => {
    onRpc("get_approval_spec", ({ args }) => {
        expect.step(`get_approval_spec: ${JSON.stringify(args)}`);
        return {
            all_rules: defaultRules,
            partner: [[[args[0][0].res_id, false, "someaction"], { rules: [1], entries: [] }]],
        };
    });

    onRpc("web_save", () => {
        expect.step("web_save");
    });

    onRpc("check_approval", ({ args }) => {
        expect.step(`check_approval: ${JSON.stringify(args)}`);
        return {
            approved: false,
            rules: [
                {
                    id: 1,
                    group_id: [1, "Internal User"],
                    domain: false,
                    can_validate: true,
                    message: false,
                    exclusive_user: false,
                },
            ],
            entries: [],
        };
    });

    await mountView({
        resModel: "partner",
        type: "form",
        resId: 1,
        arch: `
        <form>
            <button type="action" name="someaction" string="Apply Method"/>
            <field name="int_field"/>
        </form>`,
    });

    await contains(".o_field_widget[name=int_field] input").click();
    await edit("10");
    expect.verifySteps([
        'get_approval_spec: [[{"model":"partner","method":false,"action_id":"someaction","res_id":1}]]',
    ]);
    await contains("button[name='someaction']").click();
    expect.verifySteps([
        "web_save",
        'check_approval: ["partner",1,false,"someaction"]',
        'get_approval_spec: [[{"model":"partner","method":false,"action_id":"someaction","res_id":1}]]',
    ]);
});

test("approval continues to sync after a component has been destroyed", async () => {
    /* This uses two exclusive buttons. When one is displayed, the other is not.
    When clicking on the first button, this changes the int_field value which
    then hides the first button and display the second one */
    onRpc("get_approval_spec", ({ args }) => {
        expect.step(`get_approval_spec: ${JSON.stringify(args)}`);
        return {
            all_rules: defaultRules,
            partner: [
                [
                    [args[0][0].res_id, args[0][0].method, args[0][0].action_id],
                    { rules: [1], entries: [] },
                ],
            ],
        };
    });

    onRpc("check_approval", () => {
        expect.step(`check_approval`);
        return {
            approved: true,
            rules: Object.values(defaultRules),
            entries: [],
        };
    });

    onRpc("someMethod", function ({ args }) {
        return this.env["partner"].write(args[0], { int_field: 1 });
    });

    onRpc("otherMethod", () => true);

    await mountView({
        resModel: "partner",
        type: "form",
        resId: 1,
        arch: `
        <form>
            <button type="object" name="someMethod" string="Apply Method" invisible="int_field == 1"/>
            <button type="object" name="otherMethod" string="Other Method" invisible="int_field != 1"/>
            <field name="int_field"/>
        </form>`,
    });

    expect.verifySteps([
        `get_approval_spec: [[{"model":"partner","method":"someMethod","action_id":false,"res_id":1}]]`,
    ]);
    await contains("button[name='someMethod']").click();
    expect.verifySteps([
        `get_approval_spec: [[{"model":"partner","method":"otherMethod","action_id":false,"res_id":1}]]`,
    ]);
    expect(
        "button[name='otherMethod'] .o_web_studio_approval .fa-circle-o-notch.fa-spin"
    ).toHaveCount(0);
    expect(
        "button[name='otherMethod'] .o_web_studio_approval .o_web_studio_approval_avatar"
    ).toHaveCount(1);
});

test("approval with domain: pager", async () => {
    onRpc("get_approval_spec", ({ args }) => {
        expect.step(`get_approval_spec: ${args[0][0].res_id}`);
        const rules = [];
        if (args[0][0].res_id === 1) {
            rules.push(1);
        }
        return {
            all_rules: defaultRules,
            partner: [
                [
                    [args[0][0].res_id, args[0][0].method, args[0][0].action_id],
                    { rules, entries: [] },
                ],
            ],
        };
    });

    await mountView({
        resModel: "partner",
        type: "form",
        resId: 1,
        resIds: [1, 2],
        arch: `
        <form>
            <button type="object" name="someMethod" string="Apply Method"/>
            <field name="int_field"/>
        </form>`,
    });

    expect.verifySteps(["get_approval_spec: 1"]);
    expect(".o_web_studio_approval_avatar").toHaveCount(1);
    await contains(".o_pager_next").click();
    expect.verifySteps(["get_approval_spec: 2"]);
    expect(".o_web_studio_approval_avatar").toHaveCount(0);
    await contains(".o_pager_previous").click();
    expect.verifySteps(["get_approval_spec: 1"]);
    expect(".o_web_studio_approval_avatar").toHaveCount(1);
});

test("approval save a record", async () => {
    Partner._records = [];
    let hasRules = true;

    onRpc("get_approval_spec", ({ args }) => {
        expect.step(`get_approval_spec: ${JSON.stringify(args[0][0].res_id)}`);
        const rules = [];
        if (args[0][0].res_id === 1 && hasRules) {
            rules.push(1);
        }
        return {
            all_rules: defaultRules,
            partner: [
                [
                    [args[0][0].res_id, args[0][0].method, args[0][0].action_id],
                    { rules, entries: [] },
                ],
            ],
        };
    });

    onRpc("web_save", ({ method, args }) => {
        expect.step(method, args);
    });

    await mountView({
        resModel: "partner",
        type: "form",
        arch: `
        <form>
            <button type="object" name="someMethod" string="Apply Method"/>
            <field name="int_field"/>
        </form>`,
    });

    expect.verifySteps(["get_approval_spec: false"]);
    expect(".o_web_studio_approval_avatar").toHaveCount(0);
    await contains(".o_form_button_save").click();
    expect(".o_web_studio_approval_avatar").toHaveCount(1);
    expect.verifySteps(["web_save", "get_approval_spec: 1"]);

    await contains(".o_field_widget[name='int_field'] input").edit(34);
    hasRules = false;
    await contains(".o_form_button_save").click();
    expect(".o_web_studio_approval_avatar").toHaveCount(0);
    expect.verifySteps(["web_save", "get_approval_spec: 1"]);
});
