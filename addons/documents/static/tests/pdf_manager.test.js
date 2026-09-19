import { describe, expect, test } from "@odoo/hoot";
import { press, queryOne } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";

import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { contains, mountWithCleanup } from "@web/../tests/web_test_helpers";

import { PdfManager } from "@documents/owl/components/pdf_manager/pdf_manager";

defineMailModels();

describe.current.tags("desktop");

class PdfManagerForTest extends PdfManager {
    async _loadAssets() {}
    async _getPdf() {
        return {
            getPage: (number) => ({ number }),
            numPages: 6,
        };
    }
    async _isBlankPage(page, canvas) {
        return false;
    }
    async _renderCanvas(page, { width, height }) {
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        return canvas;
    }
}

function mountPdfManager() {
    return mountWithCleanup(PdfManagerForTest, {
        props: {
            documents: [
                {
                    id: 1,
                    name: "yop",
                    mimetype: "application/pdf",
                    available_embedded_actions_ids: [1, 2],
                },
                {
                    id: 2,
                    name: "blip",
                    mimetype: "application/pdf",
                    available_embedded_actions_ids: [1],
                },
            ],
            embeddedActions: [
                { id: 1, name: "action1" },
                { id: 2, name: "action2" },
            ],
            onProcessDocuments: async () => {},
            close: () => {},
        },
    });
}

test(`Pdf Manager basic rendering`, async () => {
    await mountPdfManager();
    expect(".o_documents_pdf_manager_top_bar").toHaveCount(1, {
        message: "There should be one top bar",
    });
    expect(".o_documents_pdf_page_viewer").toHaveCount(1, {
        message: "There should be one page viewer",
    });
    expect(".o_pdf_manager_button:eq(0)").toHaveText("Split", {
        message: "There should be a split button",
    });
    expect(".o_pdf_manager_button:eq(2)").toHaveText("ADD FILE", {
        message: "There should be a ADD FILE button",
    });
    expect(".o_pdf_manager_button:eq(3)").toHaveText("ACTION1", {
        message: "There should be a ACTION1 button",
    });
    expect(".o_pdf_manager_button:eq(4)").toHaveText("ACTION2", {
        message: "There should be a ACTION2 button",
    });
    expect(".o_pdf_separator_selected").toHaveCount(1, {
        message: "There should be one active separator",
    });
    expect(".o_pdf_page").toHaveCount(12, { message: "There should be 12 pages" });
    expect(".o_documents_pdf_button_wrapper").toHaveCount(12, {
        message: "There should be 12 button wrappers",
    });
    expect(".o_pdf_group_name_wrapper").toHaveCount(2, {
        message: "There should be 2 name plates",
    });
});

test(`Pdf Manager: page interactions`, async () => {
    await mountPdfManager();

    expect(".o_pdf_separator_selected").toHaveCount(1, {
        message: "There should be one active separator",
    });

    await contains(".o_page_splitter_wrapper:eq(1)").click();
    expect(".o_pdf_separator_selected").toHaveCount(2, {
        message: "There should be 2 active separator",
    });
    expect(".o_pdf_page_selected").toHaveCount(12, {
        message: "There should be 12 selected pages",
    });

    await contains(".o_documents_pdf_page_selector:eq(3)").click();
    expect(".o_pdf_page_selected").toHaveCount(11, { mesage: "There should be 11 selected pages" });
});

test(`Pdf Manager: drag & drop`, async () => {
    await mountPdfManager();

    expect(".o_pdf_separator_selected").toHaveCount(1, {
        message: "There should be one active separator",
    });
    expect(".o_documents_pdf_page_frame:eq(6) .o_pdf_name_display").toHaveCount(1, {
        message: "The seventh page should have a name plate",
    });

    await contains(".o_documents_pdf_canvas_wrapper:eq(11)").dragAndDrop(
        ".o_documents_pdf_canvas_wrapper:eq(0)",
        null,
        {
            dataTransfer: new DataTransfer(),
        }
    );
    expect(".o_pdf_separator_selected").toHaveCount(1, {
        message: "There should be one active separator",
    });
    expect(".o_documents_pdf_page_frame:eq(6) .o_pdf_name_display").toHaveCount(0, {
        message: "The seventh page shouldn't have a name plate",
    });
    expect(".o_documents_pdf_page_frame:eq(7) .o_pdf_name_display").toHaveCount(1, {
        message: "The eight page should have a name plate",
    });
});

test(`Pdf Manager: select/Unselect all pages`, async () => {
    await mountPdfManager();

    await contains(".o_documents_pdf_page_viewer").click();
    expect(".o_pdf_page_selected").toHaveCount(0, { message: "There should be no page selected" });

    await press(["ctrl", "a"]);
    await animationFrame();
    expect(".o_pdf_page_selected").toHaveCount(12, {
        message: "There should be 12 pages selected",
    });

    await press(["ctrl", "a"]);
    await animationFrame();
    expect(".o_pdf_page_selected").toHaveCount(0, { message: "There should be no page selected" });
});

test(`Pdf Manager: select pages with mouse area selection`, async () => {
    await mountPdfManager();

    await press(["ctrl", "a"]);
    await animationFrame();
    expect(".o_pdf_page_selected").toHaveCount(0, { message: "There should be no page selected" });

    const viewer = queryOne(".o_documents_pdf_manager");
    const { top, left, width, height } = viewer.getBoundingClientRect();
    const { drop, moveTo } = await contains(".o_documents_pdf_manager").drag({
        position: { x: left, y: top },
    });
    const position = { x: left + width, y: top + height };
    // 2 test events are needed to trigger the changes in the DOM. Due to rerendering of state variables
    await moveTo({ position });
    await drop({ position });
    expect(".o_pdf_page_selected").toHaveCount(12, {
        message: "There should be 12 pages selected",
    });
});

test("Pdf Manager: puts separators on active pages by pressing control+s", async () => {
    await mountPdfManager();

    await contains(".o_documents_pdf_page_viewer").click();
    expect(".o_pdf_page_selected").toHaveCount(0, { message: "There should be no page selected" });

    await press(["ctrl", "a"]);
    await animationFrame();
    expect(".o_pdf_page_selected").toHaveCount(12, {
        message: "There should be 12 pages selected",
    });

    await press(["ctrl", "s"]);
    await animationFrame();
    expect(".o_pdf_separator_selected").toHaveCount(11, {
        message: "There should be 11 active separators",
    });
});

test(`Pdf Manager: click on page bottom area selects the page`, async () => {
    await mountPdfManager();

    await contains(".o_documents_pdf_page_viewer").click();
    expect(".o_pdf_page_selected").toHaveCount(0, { message: "There should be no page selected" });

    await contains(".o_bottom_selection").click();
    expect(".o_pdf_page_selected").toHaveCount(1, { message: "There should be one page selected" });
});

test(`Pdf Manager: click on page selector selects the page`, async () => {
    await mountPdfManager();

    await contains(".o_documents_pdf_page_viewer").click();
    expect(".o_pdf_page_selected").toHaveCount(0, { message: "There should be no page selected" });

    await contains(".o_documents_pdf_page_selector").click();
    expect(".o_pdf_page_selected").toHaveCount(1, { message: "There should be one page selected" });
});

test(`Pdf Manager: arrow navigation`, async () => {
    await mountPdfManager();

    await contains(".o_documents_pdf_page_viewer").click();
    expect(".o_pdf_page_selected").toHaveCount(0, { message: "There should be no page selected" });

    await press("arrowRight");
    await animationFrame();
    expect(".o_documents_pdf_page_frame:eq(0) .o_pdf_page_focused").toHaveCount(1, {
        message: "The first page should be focused",
    });

    await press("arrowRight");
    await animationFrame();
    expect(".o_documents_pdf_page_frame:eq(1) .o_pdf_page_focused").toHaveCount(1, {
        message: "The first page should be focused",
    });
});

test(`Pdf Manager: arrow navigation + shift page activation`, async () => {
    await mountPdfManager();

    await contains(".o_documents_pdf_page_viewer").click();
    expect(".o_pdf_page_selected").toHaveCount(0, { message: "There should be no page selected" });

    await press(["shift", "arrowRight"]);
    await animationFrame();
    expect(".o_documents_pdf_page_frame:eq(0) .o_pdf_page_focused").toHaveCount(1, {
        message: "The first page should be focused",
    });

    await press(["shift", "arrowRight"]);
    await animationFrame();
    expect(".o_documents_pdf_page_frame:eq(1) .o_pdf_page_focused").toHaveCount(1, {
        message: "The second page should be focused",
    });

    await press(["shift", "arrowRight"]);
    await animationFrame();
    expect(".o_documents_pdf_page_frame:eq(2) .o_pdf_page_focused").toHaveCount(1, {
        message: "The third page should be focused",
    });
    expect(".o_pdf_page_selected").toHaveCount(3, { message: "3 pages should be selected" });

    await press(["shift", "arrowLeft"]);
    await press(["shift", "arrowLeft"]);
    await animationFrame();
    expect(".o_documents_pdf_page_frame:eq(0) .o_pdf_page_focused").toHaveCount(1, {
        message: "The first page should be focused",
    });
    expect(".o_pdf_page_selected").toHaveCount(1, { message: "One page should be selected" });
});

test(`Pdf Manager: ctrl+shift+arrow shortcut multiple activation`, async () => {
    await mountPdfManager();

    await contains(".o_documents_pdf_page_viewer").click();
    expect(".o_pdf_page_selected").toHaveCount(0, { message: "There should be no page selected" });

    await press("arrowRight");
    await press(["shift", "ctrl", "arrowRight"]);
    await animationFrame();
    expect(".o_pdf_page_selected").toHaveCount(6, { message: "There should be 6 pages selected" });
});

test(`Pdf Manager: ctrl+arrow shortcut navigation between groups`, async () => {
    await mountPdfManager();

    await contains(".o_documents_pdf_page_viewer").click();
    expect(".o_pdf_page_selected").toHaveCount(0, { message: "There should be no page selected" });

    await press("arrowRight");
    await press(["ctrl", "arrowRight"]);
    await animationFrame();
    expect(".o_documents_pdf_page_frame:eq(6) .o_pdf_page_focused").toHaveCount(1, {
        message: "The seventh page should be focused",
    });
});

test(`Pdf Manager: click on group name should select all the group`, async () => {
    await mountPdfManager();

    await contains(".o_documents_pdf_page_viewer").click();
    expect(".o_pdf_page_selected").toHaveCount(0, { message: "There should be no page selected" });

    await contains(".o_pdf_name_display").click();
    expect(".o_pdf_page_selected").toHaveCount(6, { message: "6 pages should be selected" });
});

test(`Pdf Manager: page preview behaviour`, async () => {
    await mountPdfManager();

    await contains(".o_documents_pdf_page_viewer").click();
    expect(".o_pdf_page_selected").toHaveCount(0, { message: "There should be no page selected" });

    await contains(".o_documents_pdf_canvas_wrapper").click();
    expect(".o_pdf_page_preview").toHaveCount(1, { message: "The previewer should be open" });
    expect(".o_page_index").toHaveText("1/12", {
        message: "Index of the first page should be displayed",
    });
    expect(".o_page_name").toHaveText("yop-p1", {
        message: "Name of the group should be displayed",
    });

    await press("arrowRight");
    await animationFrame();
    expect(".o_page_index").toHaveText("2/12", {
        message: "Index of the second page should be displayed",
    });
    expect(".o_page_name").toHaveText("yop-p2", {
        message: "Name of the group should be displayed",
    });
});
