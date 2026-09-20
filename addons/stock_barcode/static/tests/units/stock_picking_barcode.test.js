import { beforeEach, expect, test } from "@odoo/hoot";
import { defineModels, getService, mountWebClient, onRpc } from "@web/../tests/web_test_helpers";
import { mailModels } from "@mail/../tests/mail_test_helpers";

import { WebClientEnterprise } from "@web_enterprise/webclient/webclient";

defineModels(mailModels);

beforeEach(() => {
    this.clientData = {
        action: {
            tag: "stock_barcode_client_action",
            type: "ir.actions.client",
            res_model: "stock.picking",
            context: {},
        },
        currentState: {
            actions: {},
            data: {
                records: {
                    "barcode.nomenclature": [
                        {
                            id: 1,
                            rule_ids: [],
                        },
                    ],
                    "stock.location": [],
                    "stock.move.line": [],
                    "stock.picking": [],
                },
                nomenclature_id: 1,
            },
            groups: {},
        },
    };
    onRpc("/stock_barcode/get_barcode_data", () => Promise.resolve(this.clientData.currentState));
});

test("exclamation-triangle when picking is done", async () => {
    const pickingRecord = {
        id: 2,
        state: "done",
        move_line_ids: [],
    };
    this.clientData.action.context.active_id = pickingRecord.id;
    this.clientData.currentState.data.records["stock.picking"].push(pickingRecord);

    await mountWebClient({ WebClient: WebClientEnterprise });
    await getService("action").doAction(this.clientData.action);
    expect(".fa-5x.fa-exclamation-triangle:not(.d-none)").toHaveCount(1, {
        message: "Should have warning icon",
    });
});

test.tags("mobile");
test("scan barcode button in mobile device", async () => {
    const pickingRecord = {
        id: 2,
        state: "done",
        move_line_ids: [],
    };
    this.clientData.action.context.active_id = pickingRecord.id;
    this.clientData.currentState.data.records["stock.picking"].push(pickingRecord);
    this.clientData.currentState.groups.group_stock_multi_locations = false;

    await mountWebClient({ WebClient: WebClientEnterprise });
    await getService("action").doAction(this.clientData.action);
    expect(".o_stock_mobile_barcode").toHaveCount(1);
});
