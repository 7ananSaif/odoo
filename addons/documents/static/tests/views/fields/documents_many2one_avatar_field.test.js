import {
    DocumentsModels,
    getDocumentsTestServerModelsData,
    makeDocumentRecordData,
} from "@documents/../tests/helpers/data";
import { makeDocumentsMockEnv } from "@documents/../tests/helpers/model";
import { expect, test } from "@odoo/hoot";
import { defineModels, mountView } from "@web/../tests/web_test_helpers";

defineModels(DocumentsModels);

test("Document many2one avatar field in kanban", async () => {
    const serverData = getDocumentsTestServerModelsData();
    const myUser = serverData["res.users"][1];
    const otherUser = { id: 10, partner_id: 10, active: false };
    serverData["res.partner"] = [
        { id: myUser.partner_id, name: "myName", email: "me@example.com" },
        { id: otherUser.partner_id, name: "otherName", email: "other@example.com", active: false },
    ];
    serverData["res.users"] = [...serverData["res.users"], otherUser];
    const folder = serverData["documents.document"][0];
    const myDoc = makeDocumentRecordData(2, "myDoc", {
        folder_id: folder.id,
        owner_id: myUser.id,
        partner_id: myUser.partner_id,
    });
    const docOfOther = makeDocumentRecordData(3, "docOfOther", {
        folder_id: folder.id,
        owner_id: otherUser.id,
        partner_id: otherUser.partner_id,
    });
    serverData["documents.document"] = [folder, myDoc, docOfOther];
    await makeDocumentsMockEnv({ serverData });
    await mountView({
        type: "kanban",
        resModel: "documents.document",
        arch: `
            <kanban>
                <templates>
                    <t t-name="card">
                        <h1><field name="name"/></h1>
                        <div t-attf-class="test-res-users-{{record.id.raw_value}}">
                            <field name="owner_id" widget="documents_many2one_avatar"/>
                        </div>
                        <div t-attf-class="test-res-partner-{{record.id.raw_value}}">
                            <field name="partner_id" widget="documents_many2one_avatar"/>                        
                        </div>
                    </t>
                </templates>
            </kanban>`,
    });
    const makeTestClass = (docId, model) => `test-${model.replace(".", "-")}-${docId}`;
    for (const [model, resId] of [
        ["res.users", myDoc.owner_id],
        ["res.partner", myDoc.partner_id],
    ]) {
        const base = makeTestClass(myDoc.id, model);
        expect(`.${base} img[data-src="/web/image/${model}/${resId}/avatar_128"]`).toHaveCount(1);
        expect(`.${base} div:contains(myName):last:not(.text-muted)`).toHaveCount(1);
        expect(`.${base} .text-muted:contains(me@example.com)`).toHaveCount(1);
        expect(`.${base} .badge:contains(You)`).toHaveCount(1);
    }
    for (const [model, resId] of [
        ["res.users", docOfOther.owner_id],
        ["res.partner", docOfOther.partner_id],
    ]) {
        const base = makeTestClass(docOfOther.id, model);
        expect(`.${base} img[data-src="/web/image/${model}/${resId}/avatar_128"]`).toHaveCount(1);
        expect(`.${base} .text-muted:contains(otherName):last`).toHaveCount(1);
        expect(`.${base} .text-muted:contains(other@example.com)`).toHaveCount(1);
        expect(`.${base} .badge:contains(You)`).toHaveCount(0);
    }
});
