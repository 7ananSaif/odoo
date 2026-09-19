import { contains, defineModels, mountView, onRpc, serverState } from "@web/../tests/web_test_helpers";
import { omit } from "@web/core/utils/objects";

import { describe, expect, test } from "@odoo/hoot";
import { waitFor, waitForNone } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";

import {
    DocumentsModels,
    getDocumentsTestServerModelsData,
    makeDocumentRecordData,
} from "@documents/../tests/helpers/data";
import { makeDocumentsMockEnv } from "@documents/../tests/helpers/model";
import {
    basicDocumentsKanbanArch,
    mountDocumentsKanbanView,
} from "@documents/../tests/helpers/views/kanban";
import { getEnrichedSearchArch } from "@documents/../tests/helpers/views/search";

const archWithTags = basicDocumentsKanbanArch.replace(
    '<field name="name"/>',
    /* xml */ `
        <field name="name"/>
        <field name="tag_ids" class="d-block text-wrap" widget="many2many_tags" options="{'color_field': 'color'}"/>
        <field name="alias_domain_id"/>
        <field name="alias_name"/>
        <field name="alias_tag_ids" class="d-block text-wrap" widget="many2many_tags" options="{'color_field': 'color'}"/>
        <field name="create_activity_type_id"/>
        <field name="mail_alias_domain_count"/>
    `
);

/**
 * Shortcut for details panel selector
 * @param selector
 * @return {string} `selector` prefixed with `".o_documents_details_panel "`.
 */
const dp = (selector) => `.o_documents_details_panel ${selector}`;

const binaryTestedValues = { tag_ids: [1, 2], owner_id: serverState.userId };
const folderTestedValues = {
    alias_id: 1,
    alias_domain_id: 1,
    alias_name: "alias",
    alias_tag_ids: [1, 2],
    mail_alias_domain_count: 2,
    owner_id: serverState.userId,
    type: "folder",
    create_activity_type_id: 1,
};

describe.current.tags("desktop");

defineModels(DocumentsModels);

onRpc("ir.model", "display_name_for", ({ args }) =>
    args[0].map((model) => ({ model, display_name: model }))
);
onRpc("/documents/touch/<access_token>", () => ({}));

test("Details panel rendering for editors", async () => {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "Testing tags", { folder_id: 1, ...binaryTestedValues }),
        makeDocumentRecordData(3, "Testing container", { folder_id: 1, ...folderTestedValues }),
    ]);
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView({ arch: archWithTags });
    await contains(".o_kanban_record:contains('Testing tags')").click();
    await contains(".o_control_panel_navigation .fa-info-circle").click();
    await animationFrame();
    expect(dp(".o_documents_details_panel_name input")).toHaveCount(1);
    expect(dp(".o_documents_details_panel_name input")).toHaveValue("Testing tags");
    expect(dp(".o_field_tags input")).toHaveCount(1);
    await contains(dp(".o_field_tags span:contains('Colorless') a")).click();
    await waitForNone(dp(".o_field_tags span:contains('Colorless')"));
    await contains(dp(".o_field_tags span:contains('Colorful') a")).click();
    expect(dp(".o_field_tags input[placeholder='Add tags...']")).toHaveCount(1);
    expect(dp("input[placeholder='No owner']")).toHaveValue("Mitchell Admin");

    await contains(".o_kanban_record:contains('Testing container')").click();
    expect(dp(".o_documents_details_panel_name input")).toHaveCount(1);
    expect(dp(".o_documents_details_panel_name input")).toHaveValue("Testing container");
    expect(dp("input[placeholder='No activity']")).toHaveValue("Email");
    expect(dp("input[placeholder='Activity assigned to']")).toHaveCount(1);

    await contains(dp(".o_field_tags span:contains('Colorless') a")).click();
    await waitForNone(dp(".o_field_tags span:contains('Colorless')"));
    await contains(dp(".o_field_tags span:contains('Colorful') a")).click();
    await waitForNone(dp(".o_field_tags span:contains('Colorful')"));
    await waitFor(dp(".o_field_tags input[placeholder='Add an alias tag...']"));
});

test("Details panel rendering for viewers - m2o/m2m values", async () => {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "Testing tags", {
            folder_id: 1,
            ...binaryTestedValues,
            user_permission: "view",
        }),
        makeDocumentRecordData(3, "Testing container", {
            folder_id: 1,
            ...folderTestedValues,
            user_permission: "view",
        }),
    ]);
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView({ arch: archWithTags });
    await contains(".o_kanban_record:contains('Testing tags')").click();
    await contains(".o_control_panel_navigation .fa-info-circle").click();
    await animationFrame();

    await waitFor(dp(".o_documents_details_panel_name span:contains('Testing Tags')"));
    expect(dp(".o_documents_details_panel_name input")).toHaveCount(0);
    expect(dp(".o_field_tags span:contains('Colorless')")).toHaveCount(1);
    expect(dp(".o_field_tags span:contains('Colorful')")).toHaveCount(1);
    expect(dp("span:contains('Mitchell Admin')")).toHaveCount(1);

    await contains(".o_kanban_record:contains('Testing container')").click();
    await waitFor(dp(".o_documents_details_panel_name span:contains('Testing Container')"));
    expect(dp(".o_field_tags input")).toHaveCount(0);
    expect(dp(".o_field_tags span:contains('Colorless')")).toHaveCount(1);
    expect(dp(".o_field_tags span:contains('Colorful')")).toHaveCount(1);
    expect(dp("div:contains('alias@odoo.com')")).toHaveCount(3); // nested wrappers
    expect(dp("span:contains('Email')")).toHaveCount(1); // activity type
    expect(dp("span:contains('No activity assignee')")).toHaveCount(1); // activity type
});

test("Details panel rendering for viewers - m2o/m2m pseudo-placeholders", async () => {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "Testing tags", { folder_id: 1, user_permission: "view" }),
        makeDocumentRecordData(3, "Testing container", {
            folder_id: 1,
            ...omit(folderTestedValues, "alias_tag_ids"),
            user_permission: "view",
        }),
    ]);
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView({ arch: archWithTags });
    await contains(".o_kanban_record:contains('Testing tags')").click();
    await contains(".o_control_panel_navigation .fa-info-circle").click();
    await animationFrame();

    await waitFor(dp(".o_documents_details_panel_name span:contains('Testing Tags')"));
    expect(dp(".o_field_tags span.o_documents_details_panel_placeholder")).toHaveText("No tags");
    await waitFor(dp("span.o_documents_details_panel_placeholder:contains('No owner')"));

    await contains(".o_kanban_record:contains('Testing container')").click();
    await waitFor(dp(".o_documents_details_panel_name span:contains('Testing Container')"));
    await waitFor(dp("div:contains('alias@odoo.com')"));
    await waitFor(dp("span:contains('No activity')"));
    expect(dp(".o_field_tags span.o_documents_details_panel_placeholder")).toHaveText(
        "No alias tags"
    );
});

test("Details panel required document name", async () => {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "Testing file", { folder_id: 1 }),
        makeDocumentRecordData(3, "Testing folder", { folder_id: 1 }),
    ]);
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView({ arch: archWithTags });
    await contains(".o_control_panel_navigation .fa-info-circle").click();
    for (const documentName of [
        "Folder 1", // Container
        "Testing folder",
        "Testing file",
    ]) {
        await contains(`.o_kanban_record:contains('${documentName}')`).click();
        await animationFrame();
        expect(dp(".o_documents_details_panel_name input")).toHaveCount(1);
        expect(dp(".o_documents_details_panel_name input")).toHaveValue(documentName);
        // Set empty name
        await contains(".o_documents_details_panel_name input").edit("");
        await animationFrame();
        expect(".o_notification").toHaveCount(1);
        expect(".o_notification").toHaveText("Name cannot be empty.");
        await contains(".o_notification .o_notification_close").click();
        expect(dp(".o_documents_details_panel_name input")).toHaveValue(documentName);
    }
});

test("Details panel root folder placeholders", async () => {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "In COMPANY"),
        makeDocumentRecordData(3, "In MY DRIVE", { owner_id: serverState.userId }),
        makeDocumentRecordData(4, "In SHARED WITH ME", { owner_id: serverState.odoobotId }),
        makeDocumentRecordData(5, "In COMPANY (readonly)", { user_permission: "view" }),
    ]);
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView({ arch: archWithTags });
    await contains(".o_control_panel_navigation .fa-info-circle").click();
    // Edit mode
    for (const [documentName, rootPlaceholder] of [
        ["In COMPANY", "Company"],
        ["In MY DRIVE", "My Drive"],
        ["In SHARED WITH ME", "Shared with me"],
    ]) {
        await contains(`.o_kanban_record:contains('${documentName}')`).click();
        await animationFrame();
        expect(dp(".o_documents_details_panel_name input")).toHaveCount(1);
        expect(dp(".o_documents_details_panel_name input")).toHaveValue(documentName);
        expect(dp(".fa-folder + .o_field_many2one input")).toHaveAttribute(
            "placeholder",
            rootPlaceholder,
            { message: "Document should have correct root folder placeholder (editors)." }
        );
    }
    // Readonly mode
    await contains(".o_kanban_record:contains('In COMPANY (readonly)')").click();
    await animationFrame();
    expect(dp(".o_documents_details_panel_name span")).toHaveCount(1);
    expect(dp(".o_documents_details_panel_name span")).toHaveText("In COMPANY (readonly)");
    expect(dp(".fa-folder + .o_field_many2one .o_documents_details_panel_placeholder")).toHaveText(
        "Company",
        { message: "Document should have correct root folder placeholder (viewers)." }
    );
});

test("Details panel should be updated when clearing a selection", async function () {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "Test file", { folder_id: 1 }),
    ]);
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView({ arch: archWithTags });
    await contains(".o_control_panel_navigation .fa-info-circle").click();
    for (const documentName of ["Folder 1", "Test file"]) {
        await contains(`.o_kanban_record:contains('${documentName}')`).click();
        await animationFrame();
        expect(dp(".o_documents_details_panel_name input")).toHaveCount(1);
        expect(dp(".o_documents_details_panel_name input")).toHaveValue(documentName);
    }
    // Clearing a selection.
    await contains(".o_unselect_all").click();
    expect(dp(".o_documents_details_panel_name input")).toHaveCount(1);
    expect(dp(".o_documents_details_panel_name input")).toHaveValue("Folder 1");
});

test("Details panel changes to folders are immediately saved and visible in the app", async function () {
    await makeDocumentsMockEnv({ serverData: getDocumentsTestServerModelsData() });
    await mountDocumentsKanbanView({ arch: archWithTags });
    await contains(".o_control_panel_navigation .fa-info-circle").click();
    await contains(
        "li.o_search_panel_category_value:contains('COMPANY') button.o_toggle_fold"
    ).click();
    let counter = 0;
    onRpc("search_panel_select_range", () => {
        counter++;
    });

    const renameTwice = async (from) => {
        expect(dp(".o_documents_details_panel_name input")).toHaveCount(1);
        expect(dp(".o_documents_details_panel_name input")).toHaveValue("Folder 1");
        expect("span.o_search_panel_label_title:contains('Folder 1')").toHaveCount(1);
        await contains(dp(".o_documents_details_panel_name input")).edit(
            `Folder Renamed from ${from}`
        );
        await animationFrame();
        expect(dp(".o_documents_details_panel_name input")).toHaveValue(
            `Folder Renamed from ${from}`
        );
        expect(
            `span.o_search_panel_label_title:contains('Folder Renamed from ${from}')`
        ).toHaveCount(1);
        await contains(dp(".o_documents_details_panel_name input")).edit("Folder 1");
        await animationFrame();
        expect(dp(".o_documents_details_panel_name input")).toHaveValue("Folder 1");
        expect("span.o_search_panel_label_title:contains('Folder 1')").toHaveCount(1);
    };

    // From container Record
    await contains(`.o_kanban_record:contains('Folder 1')`).click({ ctrlKey: true });
    await animationFrame();
    await renameTwice("container");
    expect(counter).toBe(2);

    // From KanbanRecord
    await contains(`.o_kanban_record:contains('Folder 1')`).click();
    await animationFrame();
    await renameTwice("kanban record");
    expect(counter).toBe(4);
});

test("All models should be displayed in the details panel", async function () {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "Test Request", { folder_id: 1 }),
    ]);
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView({ arch: archWithTags });
    await contains(".o_kanban_record:contains('Test Request')").click();
    await contains(".o_control_panel_navigation .fa-info-circle").click();
    await animationFrame();

    await contains(dp("input[placeholder='No linked model']")).click();
    await animationFrame();
    expect(dp("div ul li")).toHaveCount(9);
    expect(dp("div ul li:contains('Start typing...')")).toHaveCount(0);
});

test("Details panel rendering", async function () {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "Testing container", {
            folder_id: 1,
            ...folderTestedValues,
            user_permission: "edit",
        }),
    ]);
    await makeDocumentsMockEnv({ serverData });
    await mountView({
        type: "list",
        resModel: "documents.document",
        arch: `<list js_class="documents_list">
        <field name="active"/>
        <field name="id"/>
        </list>`,
        searchViewArch: getEnrichedSearchArch(),
    });
    await contains(`.o_data_row td[name="id"]:contains(2)`).click();
    await contains(".o_control_panel_navigation .fa-info-circle").click();
    expect(dp(".o_documents_details_panel_name input")).toHaveValue("Testing container");
    expect(dp(".fa-envelope + div .o_field_char input")).toHaveValue("alias");
});

test("Add from document from log a note", async () => {
    onRpc("ir.model", "display_name_for", ({ args }) =>
        args[0].map((model) => ({ model, display_name: model }))
    );
    onRpc("documents.document", "add_documents_attachment", ({ args }) => {
        expect(args).toEqual([[12], "mail.compose.message", 0]);
        expect.step("add_documents_attachment");
        return [
            {
                id: 1002,
                name: "File 2",
                type: "binary",
                res_id: 0,
                res_model: "mail.compose.message",
                mimetype: "text/plain",
                public: false,
                original_id: [12, "File 2"],
            },
        ];
    });
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "Folder 2", { type: "folder" }),
        makeDocumentRecordData(11, "File 1", {
            attachment_id: 101,
            user_folder_id: "1",
            type: "binary",
        }),
        makeDocumentRecordData(12, "File 2", {
            attachment_id: 102,
            user_folder_id: "2",
            type: "binary",
        }),
    ]);
    serverData["ir.attachment"] = [
        { id: 101, name: "File 1", mimetype: "text/plain" },
        { id: 102, name: "File 2", mimetype: "text/plain" },
    ];
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView({ arch: archWithTags });

    await contains(".o_kanban_record:contains('File 1')").click();
    await contains(".o_control_panel_navigation .fa-info-circle").click();
    await waitFor(".o_document_chatter_container button.o-mail-Chatter-logNote:not(:disabled)");

    await contains(".o_document_chatter_container button.o-mail-Chatter-logNote").click();
    await contains(".o_document_chatter_container button[title='Add from Documents']").click();
    await contains(
        ".o_select_create_dialog_content .o_search_panel_label_title:contains('Company')"
    ).click();
    await contains(
        ".o_select_create_dialog_content .o_search_panel_label_title:contains('Folder 2')"
    ).click();
    // As defining a list view interferes with the view behind the modal, we select "File 2" as only child of Folder 2.
    await contains(".o_select_create_dialog_content .o_data_row .o-checkbox input").click();
    await contains(".o_select_create_dialog_content button:contains('Add from Documents')").click();

    // The attachment has been added in the composer.
    expect(".o-mail-Composer .o-mail-Attachment-hoverImageText:contains('File 2')").toHaveCount(1);
    // But the attachment is not linked to the thread.
    expect(".o-mail-Chatter-topbar .o-mail-Chatter-attachFiles:contains('1')").toHaveCount(0);
    await expect.waitForSteps(["add_documents_attachment"]);
});
