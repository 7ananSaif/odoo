import {
    DocumentsModels,
    getDocumentsTestServerModelsData,
    makeDocumentRecordData,
} from "@documents/../tests/helpers/data";
import { makeDocumentsMockEnv } from "@documents/../tests/helpers/model";
import { expect, test } from "@odoo/hoot";
import { contains, defineModels, mountView } from "@web/../tests/web_test_helpers";

defineModels(DocumentsModels);

test("Document boolean icon field in kanban", async () => {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "myDoc", {
            folder_id: 1,
            is_favorited: true,
        }),
    ]);
    const documents = serverData["documents.document"];
    await makeDocumentsMockEnv({ serverData });
    await mountView({
        type: "kanban",
        resModel: "documents.document",
        arch: `
            <kanban>
                <templates>
                    <t t-name="card">
                        <h1><field name="name"/></h1>
                        <div t-attf-class="test-{{record.id.raw_value}}">
                            <field name="is_favorited" widget="documents_boolean_icon"
                                options="{'icon': 'fa-fw fa-times', 'btn_false_class': 'btn-danger', 'btn_true_class': 'btn-success'}"/>
                        </div>
                    </t>
                </templates>
            </kanban>`,
    });
    for (const doc of documents) {
        const base = `test-${doc.id}`;
        expect(`.${base} i.fa-fw`).toHaveCount(1);
        expect(`.${base} i.fa-times`).toHaveCount(1);
        if (doc.is_favorited) {
            expect(`.${base} button`).toHaveClass("btn btn-success");
            await contains(`.${base} button`).click();
            expect(`.${base} button`).toHaveClass("btn btn-danger");
        } else {
            expect(`.${base} button`).toHaveClass("btn btn-danger");
            await contains(`.${base} button`).click();
            expect(`.${base} button`).toHaveClass("btn btn-success");
        }
    }
});
