import {
    DocumentsModels,
    getDocumentsTestServerModelsData,
} from "@documents/../tests/helpers/data";
import { makeDocumentsMockEnv } from "@documents/../tests/helpers/model";
import { destroy, expect, test } from "@odoo/hoot";
import { contains, defineModels, mountView } from "@web/../tests/web_test_helpers";

defineModels(DocumentsModels);

test("Documents mixed selection field in form", async () => {
    const testCases = [
        ["mixed", false, ["Editor", "Viewer", "None", "Mixed rights"]],
        ["view", false, ["Editor", "Viewer", "None"]],
        ["edit", false, ["Editor", "Viewer", "None"]],
        ["edit", null, ["Editor", "Viewer", "None"]],
        ["mixed", true, ["Editor", "Viewer", "Mixed rights"]],
        ["view", true, ["Editor", "Viewer"]],
        ["edit", true, ["Editor", "Viewer"]],
    ];
    const serverData = {
        ...getDocumentsTestServerModelsData(),
        "documents.sharing": testCases.map(
            ([originalAccessInternal, excludeNone, expectedOptions], idx) => ({
                id: idx + 1, // id can't be 0
                access_internal: originalAccessInternal,
            })
        ),
    };
    await makeDocumentsMockEnv({ serverData });
    for (const [
        idx,
        [originalAccessInternal, excludeNone, expectedOptions],
    ] of testCases.entries()) {
        const resId = idx + 1;
        const options =
            excludeNone === null ? "{}" : `{'exclude_none': ${excludeNone ? "True" : "False"}}`;
        const view = await mountView({
            resModel: "documents.sharing",
            type: "form",
            arch: `
                <form>
                    <field name="id"/>
                    <field name="access_internal" widget="documents_mixed_selection" options="${options}"
                        class="test${resId}"/>
                </form>
            `,
            viewId: resId,
            resId: resId,
        });

        const testCase = `(${originalAccessInternal}, ${excludeNone})`;
        expect(`.test${resId}.o_field_documents_mixed_selection`).toHaveCount(1, {
            message: `${testCase}: Should have rendered outer div`,
        });
        await contains(`.test${resId}.o_field_documents_mixed_selection input`).click();
        expect(".o-dropdown-item").toHaveCount(expectedOptions.length, { message: testCase });
        for (const expectedOption of expectedOptions) {
            expect(`.o-dropdown-item div:contains(${expectedOption})`).toHaveCount(1, {
                message: `${testCase}: ${expectedOption} option must be present with option: ${options}`,
            });
        }
        await contains(`.test${resId}.o_field_documents_mixed_selection input`).click();
        destroy(view);
    }
});
