import { expect, test } from "@odoo/hoot";
import { waitFor } from "@odoo/hoot-dom";
import {
    contains,
    defineModels,
    fields,
    models,
    mountView,
    onRpc,
    sortableDrag,
} from "@web/../tests/web_test_helpers";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";

class Report extends models.Model {
    _name = "report";

    line_ids = fields.One2many({ relation: "report_lines", relation_field: "report_id" });

    _records = [
        {
            id: 1,
            line_ids: [1, 2, 3, 4, 5],
        },
    ];
    _views = {
        form: /* xml */ `
            <form>
                <field class="w-100" name="line_ids" widget="account_report_lines_list_x2many">
                    <list>
                        <field name="id" column_invisible="1"/>
                        <field name="sequence" column_invisible="1"/>
                        <field name="parent_id" column_invisible="1"/>
                        <field name="hierarchy_level" column_invisible="1"/>
                        <field name="name"/>
                        <field name="code" optional="hide"/>
                    </list>
                </field>
            </form>
        `,
    };
}
class ReportLines extends models.Model {
    _name = "report_lines";

    report_id = fields.Many2one({ relation: "report", string: "Report ID" });
    sequence = fields.Integer();
    parent_id = fields.Many2one({ relation: "report_lines", relation_field: "id" });
    hierarchy_level = fields.Integer();
    name = fields.Char();
    code = fields.Char();

    _records = [
        {
            id: 1,
            parent_id: false,
            hierarchy_level: 1,
            name: "Root without children",
            code: "RWOC",
        },
        {
            id: 2,
            parent_id: false,
            hierarchy_level: 0,
            name: "Root with children",
            code: "RC",
        },
        {
            id: 3,
            parent_id: 2,
            hierarchy_level: 3,
            name: "Child #1",
            code: "C1",
        },
        {
            id: 4,
            parent_id: 3,
            hierarchy_level: 5,
            name: "Grandchild",
            code: "GC",
        },
        {
            id: 5,
            parent_id: 2,
            hierarchy_level: 3,
            name: "Child #2",
            code: "C2",
        },
    ];

    _views = {
        form: `<form><field name="name"/></form>`,
    };
}
defineModels([Report, ReportLines]);
defineMailModels();

//------------------------------------------------------------------------------------------------------------------
// Structure
//------------------------------------------------------------------------------------------------------------------
test("have correct descendants count", async () => {
    await mountView({
        type: "form",
        resId: 1,
        resModel: "report",
    });

    expect(
        ".account_report_lines_list_x2many li[data-descendants_count='0'] span:contains('Root without children')"
    ).toHaveCount(1);
    expect(
        ".account_report_lines_list_x2many li[data-descendants_count='3'] span:contains('Root with children')"
    ).toHaveCount(1);
    expect(
        ".account_report_lines_list_x2many li[data-descendants_count='1'] span:contains('Child #1')"
    ).toHaveCount(1);
    expect(
        ".account_report_lines_list_x2many li[data-descendants_count='0'] span:contains('Grandchild')"
    ).toHaveCount(1);
    expect(
        ".account_report_lines_list_x2many li[data-descendants_count='0'] span:contains('Child #2')"
    ).toHaveCount(1);
});

//------------------------------------------------------------------------------------------------------------------
// Create
//------------------------------------------------------------------------------------------------------------------
test("can create a line", async () => {
    await mountView({
        type: "form",
        resId: 1,
        resModel: "report",
    });

    await contains(".account_report_lines_list_x2many li:last-of-type a").click();
    await waitFor(".o_dialog");

    await contains("div[name='name'] input").edit("Created line");
    await contains(".o_dialog .o_form_button_save").click();

    await waitFor(".account_report_lines_list_x2many li span:contains('Created line')");
});

//------------------------------------------------------------------------------------------------------------------
// Edit
//------------------------------------------------------------------------------------------------------------------
test("can edit a line", async () => {
    await mountView({
        type: "form",
        resId: 1,
        resModel: "report",
    });

    await contains(".account_report_lines_list_x2many li[data-record_id='1'] .column").click();
    await waitFor(".o_dialog");

    await contains("div[name='name'] input").edit("Line without children (edited)");
    await contains(".o_dialog .o_form_button_save").click();

    await waitFor(
        ".account_report_lines_list_x2many li span:contains('Line without children (edited)')"
    );
});

//------------------------------------------------------------------------------------------------------------------
// Delete
//------------------------------------------------------------------------------------------------------------------
test("can delete a root", async () => {
    await mountView({
        type: "form",
        resId: 1,
        resModel: "report",
    });

    await contains(
        ".account_report_lines_list_x2many li[data-record_id='1'] > div > .trash"
    ).click();

    expect(
        ".account_report_lines_list_x2many li span:contains('Root without children')"
    ).toHaveCount(0);
    expect(".account_report_lines_list_x2many li span:contains('Root with children')").toHaveCount(
        1
    );
    expect(".account_report_lines_list_x2many li span:contains('Child #1')").toHaveCount(1);
    expect(".account_report_lines_list_x2many li span:contains('Grandchild')").toHaveCount(1);
    expect(".account_report_lines_list_x2many li span:contains('Child #2')").toHaveCount(1);
});

test("can delete a root with children", async () => {
    await mountView({
        type: "form",
        resId: 1,
        resModel: "report",
    });

    await contains(
        ".account_report_lines_list_x2many li[data-record_id='2'] > div > .trash"
    ).click();

    // Confirmation dialog "This line and all its children will be deleted. Are you sure you want to proceed?"
    await waitFor(".o_dialog");
    await contains(".o_dialog .btn-primary").click();

    expect(
        ".account_report_lines_list_x2many li span:contains('Root without children')"
    ).toHaveCount(1);
    expect(".account_report_lines_list_x2many li span:contains('Root with children')").toHaveCount(
        0
    );
    expect(".account_report_lines_list_x2many li span:contains('Child #1')").toHaveCount(0);
    expect(".account_report_lines_list_x2many li span:contains('Grandchild')").toHaveCount(0);
    expect(".account_report_lines_list_x2many li span:contains('Child #2')").toHaveCount(0);
});

test("can delete a last child", async () => {
    await mountView({
        type: "form",
        resId: 1,
        resModel: "report",
    });

    await contains(
        ".account_report_lines_list_x2many li[data-record_id='4'] > div > .trash"
    ).click();

    expect(
        ".account_report_lines_list_x2many li span:contains('Root without children')"
    ).toHaveCount(1);
    expect(
        ".account_report_lines_list_x2many li[data-descendants_count='2'] span:contains('Root with children')"
    ).toHaveCount(1);
    expect(
        ".account_report_lines_list_x2many li[data-descendants_count='0'] span:contains('Child #1')"
    ).toHaveCount(1);
    expect(".account_report_lines_list_x2many li span:contains('Grandchild')").toHaveCount(0);
    expect(".account_report_lines_list_x2many li span:contains('Child #2')").toHaveCount(1);
});

//------------------------------------------------------------------------------------------------------------------
// Drag and drop
//------------------------------------------------------------------------------------------------------------------
test("can move a root down", async () => {
    Report._records[0].line_ids = [1, 2, 3, 4];
    ReportLines._records = [
        {
            id: 1,
            parent_id: false,
            hierarchy_level: 1,
            name: "dragged",
            code: "D",
        },
        {
            id: 2,
            parent_id: false,
            hierarchy_level: 1,
            name: "noChild",
            code: "N",
        },
        {
            id: 3,
            parent_id: false,
            hierarchy_level: 0,
            name: "parent",
            code: "P",
        },
        {
            id: 4,
            parent_id: 3,
            hierarchy_level: 3,
            name: "child",
            code: "C",
        },
    ];

    onRpc("report", "web_save", (args) => {
        expect.step("web_save");
        const lineIds = args.args[1].line_ids;

        // Parents
        expect(lineIds[0][2].parent_id).toBe(3);

        // Hierarchy levels
        expect(lineIds[0][2].hierarchy_level).toBe(3);

        // Sequences
        expect(lineIds[0][2].sequence).toBe(4);
        expect(lineIds[1][2].sequence).toBe(1);
        expect(lineIds[2][2].sequence).toBe(2);
        expect(lineIds[3][2].sequence).toBe(3);
    });
    await mountView({
        type: "form",
        resId: 1,
        resModel: "report",
    });

    const { drop, moveUnder } = await sortableDrag("li[data-record_id='1']");

    await moveUnder("li[data-record_id='2']");
    await moveUnder("li[data-record_id='4']");
    await drop();

    await contains(".o_form_button_save").click();
    expect.verifySteps(["web_save"]);
});

test("can move a root up", async () => {
    Report._records[0].line_ids = [1, 2, 3, 4];
    ReportLines._records = [
        {
            id: 1,
            parent_id: false,
            hierarchy_level: 0,
            name: "parent",
            code: "P",
        },
        {
            id: 2,
            parent_id: 1,
            hierarchy_level: 3,
            name: "child",
            code: "C",
        },
        {
            id: 3,
            parent_id: false,
            hierarchy_level: 1,
            name: "noChild",
            code: "N",
        },
        {
            id: 4,
            parent_id: false,
            hierarchy_level: 1,
            name: "dragged",
            code: "D",
        },
    ];

    onRpc("report", "web_save", (args) => {
        expect.step("web_save");
        const lineIds = args.args[1].line_ids;

        // Parents
        expect(lineIds[0][2].parent_id).toBe(1);

        // Hierarchy levels
        expect(lineIds[0][2].hierarchy_level).toBe(3);

        // Sequences
        expect(lineIds[0][2].sequence).toBe(2);
        expect(lineIds[1][2].sequence).toBe(1);
        expect(lineIds[2][2].sequence).toBe(3);
        expect(lineIds[3][2].sequence).toBe(4);
    });
    await mountView({
        type: "form",
        resId: 1,
        resModel: "report",
    });

    const { drop, moveAbove } = await sortableDrag("li[data-record_id='4']");

    await moveAbove("li[data-record_id='3']");
    await moveAbove("li[data-record_id='2']");
    await drop();

    await contains(".o_form_button_save").click();
    expect.verifySteps(["web_save"]);
});

test("can move a child down", async () => {
    Report._records[0].line_ids = [1, 2, 3, 4];
    ReportLines._records = [
        {
            id: 1,
            parent_id: false,
            hierarchy_level: 0,
            name: "parent",
            code: "P",
        },
        {
            id: 2,
            parent_id: 1,
            hierarchy_level: 3,
            name: "dragged",
            code: "D",
        },
        {
            id: 3,
            parent_id: 1,
            hierarchy_level: 3,
            name: "child",
            code: "C",
        },
        {
            id: 4,
            parent_id: false,
            hierarchy_level: 1,
            name: "noChild",
            code: "N",
        },
    ];

    onRpc("report", "web_save", (args) => {
        expect.step("web_save");
        const lineIds = args.args[1].line_ids;

        // Parents
        expect(lineIds[0][2].parent_id).toBe(false);

        // Hierarchy levels
        expect(lineIds[0][2].hierarchy_level).toBe(1);

        // Sequences
        expect(lineIds[0][2].sequence).toBe(4);
        expect(lineIds[1][2].sequence).toBe(1);
        expect(lineIds[2][2].sequence).toBe(2);
        expect(lineIds[3][2].sequence).toBe(3);
    });
    await mountView({
        type: "form",
        resId: 1,
        resModel: "report",
    });

    const { drop, moveUnder } = await sortableDrag("li[data-record_id='2']");

    await moveUnder("li[data-record_id='3']");
    await moveUnder("li[data-record_id='4']");
    await drop();

    await contains(".o_form_button_save").click();
    expect.verifySteps(["web_save"]);
});

test("can move a child up", async () => {
    Report._records[0].line_ids = [1, 2, 3];
    ReportLines._records = [
        {
            id: 1,
            parent_id: false,
            hierarchy_level: 0,
            name: "parent",
            code: "P",
        },
        {
            id: 2,
            parent_id: 1,
            hierarchy_level: 3,
            name: "child",
            code: "C",
        },
        {
            id: 3,
            parent_id: 1,
            hierarchy_level: 3,
            name: "dragged",
            code: "D",
        },
    ];

    onRpc("report", "web_save", (args) => {
        expect.step("web_save");
        const lineIds = args.args[1].line_ids;

        // Parents
        expect(lineIds[0][2].parent_id).toBe(false);

        // Hierarchy levels
        expect(lineIds[0][2].hierarchy_level).toBe(1);

        // Sequences
        expect(lineIds[0][2].sequence).toBe(1);
        expect(lineIds[1][2].sequence).toBe(2);
        expect(lineIds[2][2].sequence).toBe(3);
    });
    await mountView({
        type: "form",
        resId: 1,
        resModel: "report",
    });

    const { drop, moveAbove } = await sortableDrag("li[data-record_id='3']");

    await moveAbove("li[data-record_id='2']");
    await moveAbove("li[data-record_id='1']");
    await drop();

    await contains(".o_form_button_save").click();
    expect.verifySteps(["web_save"]);
});

test("can move a new root into a child", async () => {
    Report._records[0].line_ids = [1, 2, 3];
    ReportLines._records = [
        {
            id: 1,
            parent_id: false,
            hierarchy_level: 0,
            name: "parent",
            code: "P",
        },
        {
            id: 2,
            parent_id: 1,
            hierarchy_level: 3,
            name: "child",
            code: "C",
        },
        {
            id: 3,
            parent_id: false,
            hierarchy_level: 1,
            name: "noChild",
            code: "N",
        },
    ];

    await mountView({
        type: "form",
        resId: 1,
        resModel: "report",
    });

    await contains(".account_report_lines_list_x2many li:last-of-type a").click();
    await contains("div[name='name'] input").edit("dragged");
    await contains(".o_dialog .o_form_button_save").click();

    const { drop, moveAbove } = await sortableDrag("li[data-record_id='4']");

    await moveAbove("li[data-record_id='3']");
    await moveAbove("li[data-record_id='2']");
    await drop();

    // Only assert web_save for the main form view, not for the dialog
    onRpc("report", "web_save", (args) => {
        expect.step("web_save");
        const lineIds = args.args[1].line_ids;

        // Parents
        expect(lineIds[0][2].parent_id).toBe(1);

        // Hierarchy levels
        expect(lineIds[0][2].hierarchy_level).toBe(3);

        // Sequences
        expect(lineIds[0][2].sequence).toBe(2);
        expect(lineIds[1][2].sequence).toBe(1);
        expect(lineIds[2][2].sequence).toBe(3);
        expect(lineIds[3][2].sequence).toBe(4);
    });

    await contains(".o_form_button_save").click();
    expect.verifySteps(["web_save"]);
});

test("can move a child into a new root", async () => {
    Report._records[0].line_ids = [];
    ReportLines._records = [];

    await mountView({
        type: "form",
        resId: 1,
        resModel: "report",
    });

    await contains(".account_report_lines_list_x2many li:last-of-type a").click();
    await contains("div[name='name'] input").edit("parent");
    await contains(".o_dialog .o_form_button_save").click();

    await contains(".account_report_lines_list_x2many li:last-of-type a").click();
    await contains("div[name='name'] input").edit("dragged");
    await contains(".o_dialog .o_form_button_save").click();

    const { drop } = await contains("li[data-record_id='2']").drag();
    await drop("li[data-record_id='2']", { position: "right", relative: true });

    // Only assert web_save for the main form view, not for the dialog
    onRpc("report", "web_save", (args) => {
        expect.step("web_save");
        const lineIds = args.args[1].line_ids;

        // Parents
        expect(lineIds[0][2].parent_id).toBe(1);

        // Hierarchy levels
        expect(lineIds[0][2].hierarchy_level).toBe(3);

        // Sequences
        expect(lineIds[0][2].sequence).toBe(2);
        expect(lineIds[1][2].sequence).toBe(1);
    });

    await contains(".o_form_button_save").click();
    expect.verifySteps(["web_save"]);
});

test.tags("desktop");
test("can display and hide 'Code' column when toggled in optional fields", async () => {
    await mountView({
        type: "form",
        resId: 1,
        resModel: "report",
    });
    // Ensure `code` column is hidden by default
    expect(".account_report_lines_list_x2many span.fw-bold.fixed:contains('Code')").toHaveCount(0);

    // simulate toggling the `code` field to make it visible
    await contains(".o-dropdown.dropdown-toggle").click();
    await contains("input[name='code']").click();

    // Check that the column is now visible
    expect(".account_report_lines_list_x2many span.fw-bold.fixed:contains('Code')").toHaveCount(1);

    // Toggle it back to hide and verify
    await contains("input[name='code']").click();
    expect(".account_report_lines_list_x2many span.fw-bold.fixed:contains('Code')").toHaveCount(0);
});
