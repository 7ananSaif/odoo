import { describe, expect, test } from "@odoo/hoot";
import {
    click,
    keyDown,
    press,
    queryAll,
    queryAllTexts,
    setInputFiles,
    waitFor,
    waitForNone,
} from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { inputFiles } from "@web/../tests/utils";
import { WebClient } from "@web/webclient/webclient";
import {
    contains,
    defineActions,
    defineModels,
    getService,
    mockService,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
    toggleSearchBarMenu,
} from "@web/../tests/web_test_helpers";

import {
    DocumentsModels,
    getDocumentsTestServerModelsData,
    makeDocumentRecordData,
    mimetypeExamplesBase64,
} from "./helpers/data";
import { makeDocumentsMockEnv } from "./helpers/model";
import { embeddedActionsServerData } from "./helpers/test_server_data";
import { basicDocumentsKanbanArch, mountDocumentsKanbanView } from "./helpers/views/kanban";
import { getEnrichedSearchArch } from "./helpers/views/search";

import { documentsClientThumbnailService } from "@documents/views/helper/documents_client_thumbnail_service";
import { EventBus } from "@odoo/owl";
import { Deferred } from "@web/core/utils/concurrency";

describe.current.tags("desktop");

defineModels(DocumentsModels);

defineActions([
    {
        id: 1,
        name: "Documents",
        res_model: "documents.document",
        views: [[false, "kanban"]],
    },
]);

test("Open share with edit user_permission", async function () {
    onRpc("/documents/touch/accessTokenFolder1", () => ({}));
    const serverData = getDocumentsTestServerModelsData();
    const { id: folder1Id, name: folder1Name } = serverData["documents.document"][0];
    mockService("document.document", {
        openSharingDialog: (documentIds) => {
            expect(documentIds).toEqual([folder1Id]);
            expect.step("open_share");
        },
    });
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView();
    await contains(`.o_kanban_record:contains(${folder1Name}) .o_record_selector`).click({
        ctrlKey: true,
    });
    await contains("button:contains(Share)").click();
    expect.verifySteps(["open_share"]);
});

test("Colorless-tags are also visible on cards", async function () {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "Testing tags", { folder_id: 1, tag_ids: [1, 2] }),
    ]);
    const { name: folder1Name } = serverData["documents.document"][0];
    const archWithTags = basicDocumentsKanbanArch.replace(
        '<field name="name"/>',
        '<field name="name"/>\n' +
            '<field name="tag_ids" class="d-block text-wrap" widget="many2many_tags" options="{\'color_field\': \'color\'}"/>'
    );
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView({ arch: archWithTags });
    await contains(`.o_kanban_record:contains(${folder1Name})`).click();
    await animationFrame();
    expect(
        ".o_kanban_record:contains('Testing tags') div[name='tag_ids'] div .o_tag:nth-of-type(1)"
    ).toHaveText("Colorless");
    expect(
        ".o_kanban_record:contains('Testing tags') div[name='tag_ids'] div .o_tag:nth-of-type(2)"
    ).toHaveText("Colorful");
});

test("Uploading from control panel", async () => {
    const _bus = new EventBus();
    mockService("file_upload", {
        bus: _bus,
        upload: (route) => {
            if (route.startsWith("/documents/upload")) {
                _bus.trigger("FILE_UPLOAD_LOADED", {
                    upload: {
                        data: new FormData(),
                        xhr: { status: 200, response: '{ "records": [] }' },
                    },
                });
                expect.step("doc uploaded");
            }
        },
    });
    const serverData = getDocumentsTestServerModelsData();
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView();
    await contains("button.btn.btn-primary.o-dropdown:contains('New')").click();
    await contains("button.btn.btn-link.o_documents_kanban_upload").click();
    // This step seems necessary to succeed everytime vs. clicking on "Upload" above...
    await contains("input.o_input_file.o_hidden", {
        visible: false,
    }).click();
    await animationFrame();
    await setInputFiles([new File(["fake_file"], "fake_file.tiff", { type: "text/plain" })]);
    await animationFrame();

    expect.verifySteps(["doc uploaded"]);
});

test("Download button availability", async function () {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "Request", { folder_id: 1 }),
        makeDocumentRecordData(3, "Binary", { attachment_id: 1, folder_id: 1 }),
    ]);
    serverData["ir.attachment"] = [{ id: 1, name: "binary" }];
    const { name: folder1Name } = serverData["documents.document"][0];
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView();
    await contains(`.o_kanban_record:contains(${folder1Name})`).click({ ctrlKey: true });
    // Folder should be downloadable
    await waitFor(".o_control_panel_actions:contains('Download')");

    await contains(`.o_kanban_record:contains(${folder1Name})`).click({ ctrlKey: true });
    // Request should not be downloadable
    await contains(".o_kanban_record:contains('Request')").click();
    await waitForNone(".o_control_panel_actions:contains('Download')");

    // Binary should be downloadable
    await contains(".o_kanban_record:contains('Binary')").click();
    await waitFor(".o_control_panel_actions:contains('Download')");
    // Multiple documents can be downloaded
    await contains(`.o_kanban_record:contains(${folder1Name})`).click({ ctrlKey: true });
    await waitFor(".o_control_panel_actions:contains('Download')");

    // Button should remain even if some records are not downloadable
    await contains(".o_kanban_record:contains('Request')").click({ ctrlKey: true });
    await waitFor(".o_control_panel_actions:contains('Download')");
});

test("Drag and Drop - Search panel expand folders", async function () {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "Sub Folder", { folder_id: 1, type: "folder" }),
        makeDocumentRecordData(3, "Test Folder", { type: "folder" }),
    ]);
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView();

    const searchPanelSelector = ".o_search_panel_category_value .o_search_panel_label_title";
    // Check that when we drag hover the Company folder it opens up to display its children
    expect(queryAllTexts(searchPanelSelector)).toEqual([
        "All",
        "Company",
        "My Drive",
        "Shared with me",
        "Recent",
        "Trash",
    ]);
    const { cancel, moveTo } = await contains(".o_kanban_record[data-value-id='3']").drag();
    await moveTo(
        ".o_search_panel_category_value[data-value-id='COMPANY'] div.o_search_panel_label"
    );
    expect(queryAllTexts(searchPanelSelector)).toEqual([
        "All",
        "Company",
        "Folder 1",
        "Test Folder",
        "My Drive",
        "Shared with me",
        "Recent",
        "Trash",
    ]);
    await moveTo(".o_search_panel_category_value[data-value-id='1'] div.o_search_panel_label");
    expect(queryAllTexts(searchPanelSelector)).toEqual([
        "All",
        "Company",
        "Folder 1",
        "Sub Folder",
        "Test Folder",
        "My Drive",
        "Shared with me",
        "Recent",
        "Trash",
    ]);
    await cancel();

    expect(queryAll(".o_record_temporary", { root: document.body })).toHaveCount(0, {
        message: "temporary cards should have been cleaned up",
    });
});

test("Drag and Drop - A folder into itself or its children", async function () {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "Sub Folder", { folder_id: 1, type: "folder" }),
        makeDocumentRecordData(3, "Folder 2", { type: "folder" }),
    ]);
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView();

    const folder1 = ".o_kanban_record[data-value-id='1']";
    const folder2 = ".o_kanban_record[data-value-id='2']";
    const folder3 = ".o_kanban_record[data-value-id='3']";

    const { cancel, moveTo } = await contains(folder1).drag();
    await moveTo(folder2);
    expect(folder2).toHaveClass("o_drag_invalid");
    expect(".o_documents_dnd_text").toHaveText(
        "You cannot move a folder into itself or a children."
    );
    await moveTo(folder3);
    expect(folder3).toHaveClass("o_drag_hover");
    expect(".o_documents_dnd_text").toHaveText("Folder 1");
    await moveTo(folder1);
    expect(folder1).toHaveClass("o_drag_invalid");
    expect(".o_documents_dnd_text").toHaveText(
        "You cannot move a folder into itself or a children."
    );
    await cancel();
});

test("Drag and Drop - After selecting multiple documents", async function () {
    const serverData = getDocumentsTestServerModelsData(
        [1, 2, 3].map((idx) =>
            makeDocumentRecordData(idx + 1, `Test Document ${idx}`, { folder_id: 1 })
        )
    );
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView();

    const document2 = ".o_kanban_record[data-value-id='2']";
    const document4 = ".o_kanban_record[data-value-id='4']";

    await contains(document2).click({ ctrlKey: true });
    await contains(document4).click({ ctrlKey: true });

    let { cancel } = await contains(document2).drag();
    expect(document2).toHaveStyle({ opacity: "0.3" });
    expect(document4).toHaveStyle({ opacity: "0.3" });
    expect(".o_documents_dnd_text").toHaveText("Test Document 1");
    await cancel();

    ({ cancel } = await contains(document4).drag());
    expect(document2).toHaveStyle({ opacity: "0.3" });
    expect(document4).toHaveStyle({ opacity: "0.3" });
    expect(".o_documents_dnd_text").toHaveText("Test Document 3");
    await cancel();
});

test("Drag and Drop - Check permission when dropping documents", async function () {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "Test Document 1"),
        makeDocumentRecordData(3, "Test Document 2", { user_permission: "view" }),
    ]);
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView();

    let { drop, moveTo } = await contains(".o_kanban_record[data-value-id='2']").drag();
    await moveTo(".o_kanban_record[data-value-id='1']");
    await drop();
    await waitFor(".o_notification");
    expect(".o_notification_content:eq(-1)").toHaveText("The document has been moved.");

    ({ drop, moveTo } = await contains(".o_kanban_record[data-value-id='3']").drag());
    await moveTo(".o_kanban_record[data-value-id='1']");
    await drop();
    await waitFor(".o_notification");
    expect(".o_notification_content:eq(-1)").toHaveText(
        "At least one document could not be moved due to access rights."
    );
});

test("Drag and Drop - Check access rights confirmation popup when moving from kanban view", async function () {
    onRpc("documents.document", "write", ({ args }) => {
        expect(args[0][0]).toBe(2);
        expect(args[1].user_folder_id).toBe("5");
        expect.step("action_move_documents");
    });
    const documents = [
        [2, "Internal Viewer - Link None - Discoverable", "view", "none", false],
        [3, "Internal Editor - Link None - Discoverable", "edit", "none", false],
        [4, "Internal Viewer - Link Viewer - Discoverable", "view", "view", false],
        [5, "Internal Viewer - Link None - Must have link", "view", "none", true],
        [6, "Internal Viewer - Link Viewer - Must have link", "view", "view", true],
    ];
    const serverData = getDocumentsTestServerModelsData(
        documents.map(([id, name, access_internal, access_via_link, is_access_via_link_hidden]) =>
            makeDocumentRecordData(id, name, {
                access_internal,
                access_via_link,
                is_access_via_link_hidden,
                type: "folder",
            })
        )
    );
    const cases = [
        [2, 3, true], // Change internal access
        [2, 4, true], // Change link access
        [2, 5, false], // Change link hidden access with link access == none
        [4, 6, true], // Change link hidden access with link access != none
    ];
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView();

    for (const [docToMove, targetDoc, expectedConfirmation] of cases) {
        const { drop, moveTo } = await contains(
            `.o_kanban_record[data-value-id='${docToMove}']`
        ).drag();
        await moveTo(`.o_kanban_record[data-value-id='${targetDoc}']`);
        await drop();
        if (expectedConfirmation) {
            // Wait for dialog, cancel move and close dialog
            await waitFor(".o_dialog:not(.o_inactive_modal)");
            expect(".o_dialog:not(.o_inactive_modal)").toHaveCount(1);
            await click(".o_dialog:not(.o_inactive_modal) .modal-footer button:contains(Cancel)");
            await animationFrame();
            expect(".o_dialog:not(.o_inactive_modal)").toHaveCount(0);
        } else {
            // Assert move
            await animationFrame();
            expect.verifySteps(["action_move_documents"]);
        }
    }
});

test("Drag and Drop - Check access rights confirmation popup when moving from search panel", async function () {
    onRpc("action_move_folder", ({ args }) => {
        expect.step(`action_move_folder_${args[0][0]}_${args[1]}`);
        expect(typeof args[1]).toBe("string");
    });
    const documents = [
        [2, "Internal Viewer - Link None - Discoverable", "view", "none", false],
        [3, "Internal Editor - Link None - Discoverable", "edit", "none", false],
        [4, "Internal Viewer - Link Viewer - Discoverable", "view", "view", false],
        [5, "Internal Viewer - Link None - Must have link", "view", "none", true],
        [6, "Internal Viewer - Link Viewer - Must have link", "view", "view", true],
    ];
    const labelByCode = { none: "None", view: "Viewer", edit: "Editor" };
    const serverData = getDocumentsTestServerModelsData(
        documents.map(([id, name, access_internal, access_via_link, is_access_via_link_hidden]) =>
            makeDocumentRecordData(id, name, {
                access_internal,
                access_via_link,
                is_access_via_link_hidden,
                type: "folder",
            })
        )
    );
    const cases = [
        [2, 3, true], // Change internal access
        [2, 4, true], // Change link access
        [2, 5, false], // Change link hidden access with link access == none
        [4, 6, true], // Change link hidden access with link access != none
    ];
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView();
    await click(".o_search_panel_category_value[data-value-id='COMPANY'] .o_toggle_fold");
    await animationFrame();

    for (const [docToMove, targetDoc, expectedConfirmation] of cases) {
        // Drag & Drop under the target folder
        const { drop, moveTo } = await contains(
            `.o_search_panel_category_value[data-value-id='${docToMove}']`
        ).drag();
        const targetFolder = document.querySelector(
            `.o_search_panel_category_value[data-value-id='${targetDoc}']`
        );
        await moveTo(targetFolder);
        await moveTo(targetFolder, {
            position: { y: targetFolder.offsetHeight },
            relative: true,
        });
        await moveTo(targetFolder, {
            position: { x: targetFolder.offsetWidth },
            relative: true,
        });
        await drop();
        await animationFrame();
        if (expectedConfirmation) {
            await waitFor(".o_dialog:not(.o_inactive_modal)");
            expect(".o_dialog:not(.o_inactive_modal)").toHaveCount(1);
            const targetFolder = documents.find((doc) => doc[0] === targetDoc);
            const accessInternal = labelByCode[targetFolder[2]];
            const accessViaLink = labelByCode[targetFolder[3]];
            expect(
                `[aria-labelledby="o_documents_access_update_confirmation_access_internal"]:contains(${accessInternal})`
            ).toBeVisible();
            expect(
                `[aria-labelledby="o_documents_access_update_confirmation_access_via_link"]:contains(${accessViaLink})`
            ).toBeVisible();
            await contains(
                ".o_dialog:not(.o_inactive_modal) .modal-footer button:contains(Cancel)"
            ).click();
            expect.step(`confirm_${docToMove}_${targetDoc}`);
            await waitForNone(".o_dialog:not(.o_inactive_modal)");
        }
    }
    // Dropping inside COMPANY
    const source = contains(".o_search_panel_category_value[data-value-id='4']");
    const { drop, moveTo } = await source.drag();
    await moveTo(document.querySelector(".o_search_panel_category_value[data-value-id='1']"));
    await drop();
    await animationFrame();
    expect.verifySteps([
        "confirm_2_3",
        "confirm_2_4",
        "action_move_folder_2_5",
        "confirm_4_6",
        "action_move_folder_4_COMPANY",
    ]);
});

test("Drag and Drop - Drop multiple documents at once", async function () {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "Test Document 1"),
        makeDocumentRecordData(3, "Test Document 2", { user_permission: "view" }),
    ]);
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView();

    await contains(".o_kanban_record[data-value-id='2']").click({ ctrlKey: true });
    await contains(".o_kanban_record[data-value-id='3']").click({ ctrlKey: true });

    const { drop, moveTo } = await contains(".o_kanban_record[data-value-id='2']").drag();
    await moveTo(".o_kanban_record[data-value-id='1']");
    await drop();
    await waitFor(".o_notification");
    expect(queryAllTexts(".o_notification_content")).toEqual([
        "At least one document could not be moved due to access rights.",
        "The document has been moved.",
    ]);
});

test("Drag and Drop - Drop document while holding CTRL", async function () {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "Test Document"),
    ]);
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView();

    const { drop, moveTo } = await contains(".o_kanban_record[data-value-id='2']").drag();
    expect(".o_documents_dnd_modifier").not.toBeVisible();
    await keyDown("Control");
    expect(".o_documents_dnd_modifier").toBeVisible();
    await moveTo(
        ".o_search_panel_category_value[data-value-id='COMPANY'] div.o_search_panel_label"
    );
    await moveTo(".o_search_panel_category_value[data-value-id='1'] div.o_search_panel_label");
    expect(".o_documents_dnd_modifier").toBeVisible(); // check after moveTo to be sure it's still visible
    await drop();
    await waitFor(".o_notification");
    expect(".o_notification_content:eq(-1)").toHaveText("A shortcut has been created.");
});

test("Lock action availability and check", async function () {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "Binary", { folder_id: 1 }),
    ]);
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView();

    const folder = ".o_kanban_record[data-value-id='1']";

    // Folder should not be lockable
    await contains(folder).click({ ctrlKey: true });
    await contains(".o_cp_action_menus button").click();
    await waitForNone(".o-dropdown--menu .o-dropdown-item:contains('Lock')");

    // Binary should be lockable
    await contains(".o_kanban_record:contains('Binary')").click();
    await contains(".o_cp_action_menus button").click();
    await contains(".o-dropdown--menu .o-dropdown-item:contains('Lock')").click();
    await waitFor(".o_kanban_record i.fa-lock");

    // Unlock the binary record
    await contains(".o_cp_action_menus button").click();
    await contains(".o-dropdown--menu .o-dropdown-item:contains('Unlock')").click();
    expect(".modal-body").toHaveText(
        "This document is locked by OdooBot.\nAre you sure you want to unlock it?"
    );
    await contains(".modal .modal-footer .btn-primary").click();
    await waitForNone(".o_kanban_record i.fa-lock");

    // Multiple documents cannot be locked
    await contains(folder).click({ ctrlKey: true });
    await contains(".o_cp_action_menus button").click();
    await waitForNone(".o-dropdown--menu .o-dropdown-item:contains('Lock')");
});

test("only show common available actions", async function () {
    await makeDocumentsMockEnv({ serverData: embeddedActionsServerData });
    await mountDocumentsKanbanView();

    await contains(`.o_kanban_record:contains('Request 1')`).click();
    await waitFor(".o_control_panel_actions:contains('Action 1')");

    await contains(`.o_kanban_record:contains('Request 2')`).click();
    await waitForNone(".o_control_panel_actions:contains('Action 1')");
    await waitFor(".o_control_panel_actions:contains('Action 2 only')");
    await waitFor(".o_control_panel_actions:contains('Action 2 and 3')");

    await contains(`.o_kanban_record:contains('Request 3')`).click({ ctrlKey: true });
    await waitForNone(".o_control_panel_actions:contains('Action 2 only')");
    await waitFor(".o_control_panel_actions:contains('Action 2 and 3')");
});

test("Thumbnail: webp thumbnail generation", async function () {
    onRpc("/documents/document/3/update_thumbnail", async (args) => {
        const { params } = await args.json();
        expect.step("thumbnail generated");
        expect(params.thumbnail.startsWith("/9j/")).toEqual(true);
        return true;
    });
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(3, "Test Document", {
            thumbnail_status: "client_generated",
            attachment_id: 2,
            folder_id: 1,
            mimetype: "image/webp",
        }),
    ]);
    serverData["ir.attachment"] = [{ id: 2, name: "binary" }];
    await makeDocumentsMockEnv({ serverData });
    patchWithCleanup(documentsClientThumbnailService, {
        _getLoadedImage() {
            const img = new Image();
            const imagePromise = new Deferred();
            img.onload = () => imagePromise.resolve(img);
            img.src = "data:image/webp;base64," + mimetypeExamplesBase64.WEBP;
            return imagePromise;
        },
    });
    await mountDocumentsKanbanView();
    expect.verifySteps(["thumbnail generated"]);
});

test("Document Request Upload", async function () {
    mockService("file_upload", {
        upload: (route, files, params) => {
            if (route === "/documents/upload/accessToken") {
                expect.step("upload_done");
            }
        },
    });

    const serverData = getDocumentsTestServerModelsData([
        {
            folder_id: 1,
            id: 2,
            name: "Test Request",
            access_token: "accessToken",
        },
    ]);

    const archWithRequest = basicDocumentsKanbanArch.replace(
        '<field name="name"/>',
        '<field name="name"/>\n' +
            '<t t-set="isRequest" t-value="record.type.raw_value === \'binary\' and !record.attachment_id.raw_value"/>\n' +
            '<input t-if="isRequest" type="file" class="o_hidden o_kanban_replace_document"/>\n'
    );
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView({ arch: archWithRequest });

    const file = new File(["hello world"], "text.txt", { type: "text/plain" });
    await inputFiles("input.o_kanban_replace_document", [file]);
    await animationFrame();
    expect.verifySteps(["upload_done"]);
});

test("focus when selecting all - ctrl + a", async function () {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "Test Document", { folder_id: 1 }),
        makeDocumentRecordData(3, "Test Document 2", { folder_id: 1 }),
    ]);
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView();

    await contains(".o_kanban_renderer").click();

    await keyDown(["Control", "a"]);
    await waitFor(".o_kanban_record[data-value-id='1']:focus");
    await waitFor(".o_selection_box");
    expect(".o_record_selected").toHaveCount(3);

    await keyDown(["Control", "a"]);
    await waitFor(".o_kanban_record[data-value-id='1']:focus");
    await waitFor(".o_searchview");
    expect(".o_record_selected").toHaveCount(0);

    // Focus another document first
    await contains(".o_kanban_record[data-value-id='3']").click();
    await keyDown(["Control", "a"]);
    await waitFor(".o_kanban_record[data-value-id='3']:focus");

    await keyDown(["Control", "a"]);
    await waitFor(".o_kanban_record[data-value-id='3']:focus");
});

test.tags("desktop");
test("document selector: include archived checkbox should not be shown", async () => {
    await mountDocumentsKanbanView();

    await toggleSearchBarMenu();
    await contains(".o_filter_menu .dropdown-item").click();
    await waitFor(".o_tree_editor_condition");

    expect(".form-switch label:contains(Include archived)").not.toHaveCount();
});

test("Split PDF button availability", async function () {
    const serverData = getDocumentsTestServerModelsData([
        {
            attachment_id: 1,
            id: 2,
            name: "text_file.txt",
            user_permission: "edit",
            mimetype: "image/webp",
        },
        {
            attachment_id: 2,
            id: 3,
            name: "pdf1.pdf",
            user_permission: "view",
            mimetype: "application/pdf",
        },
        {
            attachment_id: 3,
            id: 4,
            name: "pdf2.pdf",
            user_permission: "edit",
            mimetype: "application/pdf",
        },
    ]);

    serverData["ir.attachment"] = [
        { id: 1, name: "text_file.txt", mimetype: "image/webp" },
        { id: 2, name: "pdf1.pdf", mimetype: "application/pdf" },
        { id: 3, name: "pdf2.pdf", mimetype: "application/pdf" },
    ];

    DocumentsModels.DocumentsDocument._views = {
        kanban: basicDocumentsKanbanArch,
        [["search", false]]: getEnrichedSearchArch(),
    };

    await makeDocumentsMockEnv({ serverData });
    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);

    // Non-PDF with edit permission in control panel
    await contains(".o_kanban_record:contains('text_file.txt') .o_record_selector").click();
    await contains(".o_dropdown_title").click();
    await waitForNone(".o-dropdown-item:contains('Split PDF')");

    // Non-PDF with edit permission in preview
    await contains(".o_kanban_record:contains('text_file.txt') [name='document_preview']").click();
    await contains(".o-FileViewer .o_cp_action_menus .o-dropdown").click();
    await waitForNone(".o-dropdown-item:contains('Split PDF')");
    await press("escape");
    await waitForNone(".o-FileViewer");

    // PDF with view permission in control panel
    await contains(".o_kanban_record:contains('pdf1.pdf') .o_record_selector").click();
    await contains(".o_dropdown_title").click();
    await waitForNone(".o-dropdown-item:contains('Split PDF')");

    // PDF with view permission in preview
    await contains(".o_kanban_record:contains('pdf1.pdf') [name='document_preview']").click();
    await contains(".o-FileViewer .o_cp_action_menus .o-dropdown").click();
    await waitForNone(".o-dropdown-item:contains('Split PDF')");
    await press("escape");
    await waitForNone(".o-FileViewer");

    // PDF with edit permission in control panel
    await contains(".o_kanban_record:contains('pdf2.pdf') .o_record_selector").click();
    await contains(".o_dropdown_title").click();
    await waitFor(".o-dropdown-item:contains('Split PDF')");

    // PDF with edit permission in preview
    await contains(".o_kanban_record:contains('pdf2.pdf') [name='document_preview']").click();
    await contains(".o-FileViewer .o_cp_action_menus .o-dropdown").click();
    await waitFor(".o-dropdown-item:contains('Split PDF')");
});

test("Export action is not available in file viewer ", async function () {
    const serverData = getDocumentsTestServerModelsData([
        {
            folder_id: 1,
            id: 2,
            url: "https://youtu.be/Ayab6wZ_U1A",
            type: "url",
        },
    ]);

    const archWithURL = basicDocumentsKanbanArch.replace(
        '<field name="name"/>',
        '<field name="name"/>\n' + '<field name="url"/>'
    );

    DocumentsModels.DocumentsDocument._views = {
        kanban: archWithURL,
        [["search", false]]: getEnrichedSearchArch(),
    };

    await makeDocumentsMockEnv({ serverData });
    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);

    await contains(
        ".o_kanban_record:contains('https://youtu.be/Ayab6wZ_U1A') .o_record_selector"
    ).click();
    await contains(".o_dropdown_title").click();
    await waitFor(".o-dropdown-item:contains('Export')");

    await contains(
        ".o_kanban_record:contains('https://youtu.be/Ayab6wZ_U1A') [name='document_preview']"
    ).click();
    await contains(".o-FileViewer .o_cp_action_menus .o-dropdown").click();
    await waitForNone(".o-dropdown-item:contains('Export')");
});

test("Control panel cog menu visibility", async function () {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "Request", { folder_id: 1 }),
    ]);
    const { name: folder1Name } = serverData["documents.document"][0];
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView();
    await waitFor(".o_kanban_renderer");

    await contains(".o_search_panel_label_title:contains('Company')").click();
    await waitFor(".o_last_breadcrumb_item:contains('Company')");
    //  There should be no cog menu on Company
    await waitForNone(".o_cp_action_menus", {});
    // There should be one on Company roots
    await contains(`.o_kanban_record:contains('${folder1Name}')`).click();
    await waitFor(`.o_last_breadcrumb_item:contains('${folder1Name}')`);
    expect(`.o_cp_action_menus`).toHaveCount(1);
});

test("Select a range with SHIFT key", async () => {
    await makeDocumentsMockEnv({ serverData: embeddedActionsServerData });
    await mountDocumentsKanbanView();
    const { name: folder1Name } = embeddedActionsServerData["documents.document"][0];
    await contains(`.o_kanban_record:contains(${folder1Name}) .o_record_selector`).click({
        ctrlKey: true,
    });
    await keyDown("Shift");
    await contains(".o_kanban_record:contains(Request 2)").click();
    expect(".o_kanban_record:contains(Request 1)").toHaveClass("o_record_selected");
    expect("div.o_record_selected").toHaveCount(3);
});

test("Name in previewer is correct without attachment", async function () {
    const serverData = getDocumentsTestServerModelsData([
        {
            id: 10,
            name: "Shin chan: The Spicy Kasukabe",
            type: "url",
            url: "https://www.youtube.com/watch?v=Qv_-R9kw5eg",
            mimetype: "text/html",
            folder_id: 1,
        },
        {
            id: 11,
            name: "Mom vs Dad |Shinchan",
            type: "url",
            url: "https://www.youtube.com/watch?v=sZeU-nrm8UA",
            mimetype: "text/html",
            folder_id: 1,
        },
    ]);

    patchWithCleanup(HTMLIFrameElement.prototype, {
        contentWindow: {
            get: () => null,
        },
        contentDocument: {
            get: () => null,
        },
    });

    const previewedAttachments = [];
    mockService("document.document", {
        setPreviewedDocument: (doc) => {
            if (doc && doc.attachment) {
                previewedAttachments.push({
                    id: doc.attachment.id,
                    name: doc.attachment.name,
                    url: doc.attachment.url,
                    documentId: doc.attachment.documentId,
                });
                expect.step(`preview_${doc.attachment.name}`);
            }
        },
        documentList: null,
    });

    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView();

    await contains(".o_kanban_record:contains('Shin chan') [name='document_preview']").click();
    await waitFor(".o-FileViewer");

    const closeBtn = document.querySelector(".o-FileViewer [aria-label='Close']");
    closeBtn.click();
    await waitForNone(".o-FileViewer");

    await contains(".o_kanban_record:contains('Mom vs Dad') [name='document_preview']").click();
    await waitFor(".o-FileViewer");

    expect(previewedAttachments).toHaveLength(2);

    expect(previewedAttachments[0].id).toBe(-10);
    expect(previewedAttachments[0].name).toBe("Shin chan: The Spicy Kasukabe");

    expect(previewedAttachments[1].id).toBe(-11);
    expect(previewedAttachments[1].name).toBe("Mom vs Dad |Shinchan");

    expect.verifySteps(["preview_Shin chan: The Spicy Kasukabe", "preview_Mom vs Dad |Shinchan"]);
});

test("Check actions with preview", async function () {
    const serverData = getDocumentsTestServerModelsData([
        {
            attachment_id: 1,
            id: 2,
            name: "Test_file.txt",
            mimetype: "image/webp",
        },
    ]);

    serverData["ir.attachment"] = [{ id: 1, name: "Test_file.txt", mimetype: "image/webp" }];

    const basicDocumentsKanbanArchWithLockUid = basicDocumentsKanbanArch.replace(
        '<field name="name"/>',
        '<field name="name"/>\n<field name="lock_uid"/>'
    );
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView({ arch: basicDocumentsKanbanArchWithLockUid });

    // Document is not locked so there should be Lock option.
    await contains(".o_kanban_record:contains('Test_file.txt') [name='document_preview']").click();
    await contains(".o-FileViewer .o_cp_action_menus .o-dropdown").click();
    await waitFor(".o-dropdown-item:contains('Lock')");
    await contains(".o-dropdown-item:contains('Lock')").click();

    // The preview should be closed when clicking the lock action.
    expect(".o-FileViewer").toHaveCount(0);

    // Document is locked so there should be Unlock option.
    await contains(".o_kanban_record:contains('Test_file.txt') [name='document_preview']").click();
    await contains(".o-FileViewer .o_cp_action_menus .o-dropdown").click();
    await waitFor(".o-dropdown-item:contains('Unlock')");
});

test("Ensure previewer shows correct name after renaming a document", async function () {
    const serverData = getDocumentsTestServerModelsData([
        {
            attachment_id: 1,
            id: 2,
            name: "text_file.txt",
            mimetype: "image/webp",
        },
    ]);

    DocumentsModels["DocumentsDocument"]._views = {
        kanban: basicDocumentsKanbanArch,
        search: getEnrichedSearchArch(),
        form: "<form><field name='name'/></form>",
    };

    serverData["ir.attachment"] = [{ id: 1, name: "text_file.txt", mimetype: "image/webp" }];

    await makeDocumentsMockEnv({ serverData });
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "documents.document",
        type: "ir.actions.act_window",
        views: [[false, "kanban"]],
    });

    await contains(".o_kanban_record:contains('text_file.txt')").click({ ctrlKey: true });
    await contains(".o_control_panel_actions button:contains('Action')").click();
    await contains(".o-dropdown-item:contains('Rename')").click();
    await contains(".o_input").edit("test1.txt");
    await contains(".o_form_button_save:contains('Save')").click();
    expect(".o_kanban_record span:contains('test1.txt')").toHaveCount(1);
    await contains(".o_kanban_record:contains('test1.txt') [name='document_preview']").click();
    await waitFor(".o-FileViewer");
    expect(".o-FileViewer-header span:contains('test1.txt')").toHaveCount(1);
});
