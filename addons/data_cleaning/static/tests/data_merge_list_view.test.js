import { expect, test } from "@odoo/hoot";
import {
    contains,
    defineModels,
    fields,
    models,
    mountView,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";

class DataMergeRecord extends models.Model {
    _name = "data_merge.record";

    name = fields.Char();
    group_id = fields.Many2one({ relation: "data_merge.group" });

    _records = [
        {
            id: 1,
            name: "a1",
            group_id: 1,
        },
        {
            id: 2,
            name: "a2",
            group_id: 1,
        },
        {
            id: 3,
            name: "b1",
            group_id: 2,
        },
        {
            id: 4,
            name: "b2",
            group_id: 2,
        },
    ];
}

class DataMergeGroup extends models.Model {
    _name = "data_merge.group";

    name = fields.Char();

    _records = [
        {
            id: 1,
            name: "1",
        },
        {
            id: 2,
            name: "2",
        },
    ];
}

defineModels([DataMergeRecord, DataMergeGroup]);
defineMailModels();

test.tags("desktop");
test("merge multiple records uses the domain selection", async () => {
    onRpc("data_merge.group", "merge_multiple_records", ({ args }) => {
        expect.step("merge_multiple_records");
        expect(args[0]).toEqual({
            1: [1, 2],
            2: [3, 4],
        });
        return true;
    });
    await mountView({
        resModel: "data_merge.record",
        type: "list",
        arch: '<list expand="true" js_class="data_merge_list"><field name="name"/></list>',
        groupBy: ["group_id"],
    });

    await contains(".o_group_header:first-child").click(); // fold the first group
    await contains("thead .o_list_record_selector").click();
    await contains(".o_selection_box .o_select_domain").click();
    await contains(".btn-primary.o_data_merge_merge_button").click();
    await contains(".modal-dialog button.btn-primary").click();

    expect.verifySteps(["merge_multiple_records"]);
});
