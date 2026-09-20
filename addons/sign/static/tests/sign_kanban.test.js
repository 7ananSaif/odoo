import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { dragoverFiles, dropFiles } from "@web/../tests/utils";
import { mountView, onRpc } from "@web/../tests/web_test_helpers";
import { defineSignModels, signModels } from "./mock_server/mock_models/sign_model";

const { IrAttachment, SignDocument, SignTemplate } = signModels;

beforeEach(() => {
    IrAttachment._records = [
        {
            id: 1,
            name: "yop.pdf",
            res_model: "sign.template",
            mimetype: "application/pdf",
        },
    ];
    SignDocument._records = [
        {
            id: 1,
            attachment_id: 1,
        },
    ];
    Object.assign(SignTemplate._records[0], { document_ids: [(6, 0, [1])] });
});

describe.current.tags("desktop");
defineSignModels();

test("Drop to upload file in kanban", async () => {
    await mountView({
        type: "kanban",
        resModel: "sign.template",
        arch: `
        <kanban js_class="sign_kanban" class="o_sign_template_kanban">
            <templates>
                <t t-name="card">
                    <field name="display_name" class="fw-bolder fs-5"/>
                </t>
            </templates>
        </kanban>`,
    });
    expect(".o_dropzone").toHaveCount(0);
    const file = new File(["test"], "test.pdf", { type: "application/pdf" });
    const fileInput = document.querySelector(".o_sign_template_file_input");
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);
    fileInput.files = dataTransfer.files;
    await dragoverFiles(".o_content", dataTransfer.files);
    await dropFiles(".o_dropzone", dataTransfer.files);
    onRpc("sign.template", "create_from_attachment_data", function ({ args, model }) {
        expect.step("attachment create");
        expect(model).toBe("sign.template");
        expect(args).toHaveLength(2);
        const attachmentID = this.env["ir.attachment"].create({
            name: args[0][0].name,
            res_model: model,
            datas: args[0][0].datas,
        });
        const signTemplateID = this.env[model].create({
            active: true,
        });
        this.env["sign.document"].create({
            template_id: signTemplateID,
            attachment_id: attachmentID,
        });
        return [signTemplateID];
    });
    expect(".o_dropzone").toHaveCount(1);
    await expect.waitForSteps(["attachment create"]);
});
