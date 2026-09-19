import { describe, expect, test } from "@odoo/hoot";
import { ViewEditorModel } from "@web_studio/client_action/view_editor/view_editor_model";

describe.current.tags("headless");

test("Sanitize string", () => {
    expect(ViewEditorModel.sanitizeString("")).toBe("");
    expect(ViewEditorModel.sanitizeString("test")).toBe("test");
    expect(ViewEditorModel.sanitizeString(" te st ")).toBe("te_st");
    expect(ViewEditorModel.sanitizeString("te-st")).toBe("te_st");
    expect(ViewEditorModel.sanitizeString("te---st te    st")).toBe("te_st_te_st");
    expect(ViewEditorModel.sanitizeString("yukulélèlàláñî")).toBe("yukulelelalani");
});
