import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";
import { _t } from "@web/core/l10n/translation";
import tourUtils from "@sign/js/tours/tour_utils";

export function createSelectionRectangle(viewerContainer, page, startPos = 0.25, endPos = 0.75) {
    const pageRect = page.getBoundingClientRect();

    const startX = pageRect.width * startPos;
    const startY = pageRect.height * startPos;
    const endX = pageRect.width * endPos;
    const endY = pageRect.height * endPos;
    const mousemoveEvent = new MouseEvent("mousemove", {
        bubbles: true,
        clientX: startX,
        clientY: startY,
    });
    viewerContainer.dispatchEvent(mousemoveEvent);

    const mousedownEvent = new MouseEvent("mousedown", {
        bubbles: true,
        clientX: startX,
        clientY: startY,
        button: 0,
    });
    viewerContainer.dispatchEvent(mousedownEvent);

    const mousemoveEvent2 = new MouseEvent("mousemove", {
        bubbles: true,
        clientX: endX,
        clientY: endY,
    });
    viewerContainer.dispatchEvent(mousemoveEvent2);

    const mouseupEvent = new MouseEvent("mouseup", {
        bubbles: true,
        clientX: endX,
        clientY: endY,
    });
    viewerContainer.dispatchEvent(mouseupEvent);
}

registry.category("web_tour.tours").add("sign_template_creation_tour", {
    url: "/odoo?debug=1",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open Sign App",
            trigger: '.o_app[data-menu-xmlid="sign.menu_document"]',
            run: "click",
        },
        {
            content: "Click on Template Menu",
            trigger: 'a[data-menu-xmlid="sign.sign_template_menu"]',
            tooltipPosition: "bottom",
            run: "click",
        },
        {
            trigger: ".o_last_breadcrumb_item > span:contains('Templates')",
        },
        {
            content: "Remove My Favorites filter",
            trigger: ".o_cp_searchview .o_facet_remove",
            run: "click",
        },
        {
            content: 'Search template "blank_template"',
            trigger: ".o_cp_searchview input",
            run: "fill blank_template",
        },
        {
            content: "Search Document Name",
            trigger: ".o_searchview_autocomplete .o-dropdown-item:first",
            run: "click",
        },
        {
            content: "Enter Template Edit Mode",
            trigger: '.o_kanban_record span:contains("blank_template")',
            run: "click",
        },
        {
            content: "Wait for iframe to load PDF",
            trigger: ":iframe #viewerContainer",
        },
        {
            content: "Wait for page to be loaded",
            trigger: ":iframe .page[data-page-number='1'] .textLayer",
            timeout: 30000, //In view mode, pdf loading can take a long time
        },
        {
            content: "Drop Signature Item",
            trigger: ".o_sign_field_type_button:contains(" + _t("Signature") + ")",
            run({ queryFirst }) {
                const to = queryFirst(`:iframe .page[data-page-number="1"]`);
                tourUtils.dragAndDropSignItemAtHeight(this.anchor, to, 0.5, 0.25);
            },
        },
        {
            content: "Drop Name Sign Item",
            trigger: ".o_sign_field_type_button:contains(" + _t("Name") + ")",
            run({ queryFirst }) {
                const to = queryFirst(`:iframe .page[data-page-number="1"]`);
                tourUtils.dragAndDropSignItemAtHeight(this.anchor, to, 0.25, 0.25);
            },
        },
        {
            content: "Drop Text Sign Item",
            trigger: ".o_sign_field_type_button:contains(" + _t("Text") + ")",
            run({ queryFirst }) {
                const to = queryFirst(`:iframe .page[data-page-number="1"]`);
                tourUtils.dragAndDropSignItemAtHeight(this.anchor, to, 0.15, 0.25);
            },
        },
        {
            content: "Test multi-select by creating a selection rectangle",
            trigger: ":iframe .page[data-page-number='1']",
            run({ queryFirst }) {
                const viewerContainer = queryFirst(`:iframe #viewerContainer`);
                const page = queryFirst(`:iframe .page[data-page-number="1"]`);
                createSelectionRectangle(viewerContainer, page, 0.25, 0.75);
            },
        },
        {
            content: "Verify items are selected",
            trigger: ":iframe .o_sign_sign_item.multi_selected",
        },
        {
            content: "Test copy functionality with Ctrl+C",
            trigger: ":iframe .o_sign_sign_item.multi_selected",
            run() {
                const keyEvent = new KeyboardEvent("keydown", {
                    key: "c",
                    code: "KeyC",
                    ctrlKey: true,
                    bubbles: true,
                });
                document.querySelector("iframe").contentDocument.dispatchEvent(keyEvent);
            },
        },
        {
            content: "Click elsewhere to prepare for paste",
            trigger: ":iframe .page[data-page-number='1']",
            run({ queryFirst, click }) {
                const page = queryFirst(`:iframe .page[data-page-number="1"]`);
                const pageRect = page.getBoundingClientRect();
                click({
                    x: pageRect.left + pageRect.width * 0.8,
                    y: pageRect.top + pageRect.height * 0.8,
                });
            },
        },
        {
            content: "Test paste functionality with Ctrl+V",
            trigger: ":iframe .page[data-page-number='1']",
            run() {
                const keyEvent = new KeyboardEvent("keydown", {
                    key: "v",
                    code: "KeyV",
                    ctrlKey: true,
                    bubbles: true,
                });
                document.querySelector("iframe").contentDocument.dispatchEvent(keyEvent);
            },
        },
        {
            content: "Test multi-select by creating a selection rectangle",
            trigger: ":iframe .page[data-page-number='1']",
            run({ queryFirst }) {
                const viewerContainer = queryFirst(`:iframe #viewerContainer`);
                const page = queryFirst(`:iframe .page[data-page-number="1"]`);
                createSelectionRectangle(viewerContainer, page, 0.25, 0.75);
            },
        },
        {
            content: "Verify items are selected",
            trigger: ":iframe .o_sign_sign_item.multi_selected",
        },
        {
            content: "Click on document name text to make it editable",
            trigger: ".o_sign_sidebar_document_name_text",
            run: "click",
        },
        {
            content: "Click document name edit button",
            trigger: ".o_sign_sidebar_document_name .fa-pencil:not(:visible)",
            run: "click",
        },
        {
            content: "Change document name",
            trigger: ".o_sign_document_name_input",
            run: "edit new-document-name && click body",
        },
        {
            trigger: ".breadcrumb .o_back_button",
            run: "click",
        },
    ],
});
