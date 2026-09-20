import {
    DocumentsModels,
    getDocumentsTestServerModelsData,
} from "@documents/../tests/helpers/data";
import { makeDocumentsMockEnv } from "@documents/../tests/helpers/model";
import { expect, test } from "@odoo/hoot";
import { contains, defineModels, mountView } from "@web/../tests/web_test_helpers";

defineModels(DocumentsModels);

test("Document discard changes in form", async () => {
    await makeDocumentsMockEnv({ serverData: getDocumentsTestServerModelsData() });
    await mountView({
        resModel: "documents.document",
        type: "form",
        arch: '<form><field name="name"/><field name="id" widget="documents_discard_changes"/></form>',
        resId: 1,
    });
    expect(".o_field_widget[name=name] input").toHaveValue("Folder 1");
    await contains(".o_field_widget[name=name] input").edit("Modified name");
    expect(".o_field_widget[name=name] input").toHaveValue("Modified name");
    await contains(".o_field_widget[name=id] button").click();
    expect(".o_field_widget[name=name] input").toHaveValue("Folder 1");
});
