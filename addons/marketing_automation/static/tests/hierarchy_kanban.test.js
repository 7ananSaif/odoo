import { defineModels, models, fields, mountView } from "@web/../tests/web_test_helpers";
import { expect, test } from "@odoo/hoot";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { queryAll, queryFirst } from "@odoo/hoot-dom";

class MarketingAutomationCampaign extends models.Model {
    _name = "marketing.automation.campaign";
    _records = [
        {
            id: 1,
            name: "Campaign 1",
            marketing_activity_ids: [1, 2, 3, 4, 5, 6],
        },
    ];
    name = fields.Char();
    marketing_activity_ids = fields.One2many({
        string: "Activities",
        relation: "marketing.automation.activity",
        relation_field: "campaign_id",
    });
}

class MarketingAutomationActivity extends models.Model {
    _name = "marketing.automation.activity";
    _records = [
        {
            id: 1,
            name: "Parent 1",
        },
        {
            id: 2,
            name: "Parent 1 > Child 1",
            parent_id: 1,
        },
        {
            id: 3,
            name: "Parent 2",
        },
        {
            id: 4,
            name: "Parent 2 > Child 1",
            parent_id: 3,
        },
        {
            id: 5,
            name: "Parent 2 > Child 2",
            parent_id: 3,
        },
        {
            id: 6,
            name: "Parent 2 > Child 2 > Child 1",
            parent_id: 5,
        },
    ];
    name = fields.Char();
    parent_id = fields.Many2one({
        string: "Parent Activity",
        relation: "marketing.automation.activity",
    });
    campaign_id = fields.Many2one({
        string: "Campaign",
        relation: "marketing.automation.campaign",
    });
}

defineModels([MarketingAutomationCampaign, MarketingAutomationActivity]);
defineMailModels();

test("render basic hierarchy kanban", async () => {
    await mountView({
        type: "form",
        resModel: "marketing.automation.campaign",
        resId: 1,
        arch: `
            <form string="Campaign">
                <sheet>
                    <group>
                        <field name="name"/>
                    </group>
                    <div>
                        <field name="marketing_activity_ids" widget="hierarchy_kanban" class="o_ma_hierarchy_container">
                            <kanban>
                                <field name="parent_id"/>
                                <templates>
                                    <div t-name="card">
                                        <div class="o_ma_body position-relative" t-att-data-record-id="record.id.raw_value">
                                            <field name="name" class="o_title"/>
                                        </div>
                                    </div>
                                </templates>
                            </kanban>
                        </field>
                    </div>
                </sheet>
            </form>`,
    });

    // Checking number of child and their positions
    const parentRecords = queryAll(
        ".o_ma_hierarchy_container .o_kanban_renderer > .o_kanban_record:not(.o_kanban_ghost):not(:empty) > .o_ma_body"
    );
    const childrenRecords = queryAll(
        ".o_ma_hierarchy_container .o_kanban_renderer > .o_kanban_record:not(.o_kanban_ghost):not(:empty) > .o_ma_body_wrapper > .o_ma_body"
    );
    const grandChildrenRecords = queryAll(
        ".o_ma_hierarchy_container .o_kanban_renderer > .o_kanban_record:not(.o_kanban_ghost):not(:empty) > .o_ma_body_wrapper > .o_ma_body_wrapper > .o_ma_body"
    );
    expect(parentRecords).toHaveCount(2);
    expect(childrenRecords).toHaveCount(3);
    expect(grandChildrenRecords).toHaveCount(1);

    // Checking titles of kanban to verify proper values
    expect(queryFirst(`.o_title`, { root: parentRecords[0] })).toHaveText("Parent 1");
    expect(queryFirst(`.o_title`, { root: parentRecords[1] })).toHaveText("Parent 2");
    expect(queryFirst(`.o_title`, { root: childrenRecords[0] })).toHaveText("Parent 1 > Child 1");
    expect(queryFirst(`.o_title`, { root: childrenRecords[1] })).toHaveText("Parent 2 > Child 1");
    expect(queryFirst(`.o_title`, { root: childrenRecords[2] })).toHaveText("Parent 2 > Child 2");
    expect(queryFirst(`.o_title`, { root: grandChildrenRecords[0] })).toHaveText(
        "Parent 2 > Child 2 > Child 1"
    );
});
