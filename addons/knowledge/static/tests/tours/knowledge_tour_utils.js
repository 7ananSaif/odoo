import { SORTABLE_TOLERANCE } from "@knowledge/components/sidebar/sidebar";
import { stepUtils } from "@web_tour/tour_utils";
import { childNodeIndex } from "@html_editor/utils/position";
import { Component, xml } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ReadonlyEmbeddedViewComponent } from "@knowledge/editor/embedded_components/backend/view/readonly_embedded_view";

const internalPermissions = {
    none: "Members only",
    read: "Can Read",
    write: "Can Edit",
};

export const openPermissionPanel = [
    {
        isActive: ["body:has(.o_knowledge_permission_panel)"],
        content: "close o_knowledge_permission_panel if it already opened",
        trigger: ".o_knowledge_header button:contains('Share')",
        run: "click",
    },
    {
        trigger: "body:not(:has(.o_knowledge_permission_panel))",
    },
    {
        trigger: ".o_knowledge_header button:contains('Share')",
        async run(helpers) {
                await new Promise((r) => setTimeout(r, 1000));
                await helpers.click();
            },
    },
    {
        trigger: "body:has(.o_knowledge_permission_panel)",
    },
];

export const changeInternalPermission = (permission) => {
    return [
        ...openPermissionPanel,
        {
            trigger: ".o_knowledge_permission_panel .o_internal_permission .dropdown-toggle",
            run: "click",
        },
        {
            trigger: `.o-dropdown-item:contains('${internalPermissions[permission]}')`,
            run: "click",
        },
    ];
};

/**
 * @param {string} name
 * @param {string} [section]
 */
export function unfoldArticleFromSidebar(name, section) {
    let trigger = section
        ? `.o_section[data-section=${section}] .o_article_name:contains(${name})`
        : `.o_article_name:contains(${name})`;
    return {
        trigger,
        run: function () {
            const handle = this.anchor.closest(".o_article_handle");
            const caret = handle.querySelector(".o_article_caret");
            caret.click();
        }
    }
}

function getOffset(element) {
    if (!element.getClientRects().length) {
        return { top: 0, left: 0 };
    }

    const rect = element.getBoundingClientRect();
    const win = element.ownerDocument.defaultView;
    return {
        top: rect.top + win.pageYOffset,
        left: rect.left + win.pageXOffset,
    };
}

/**
 * Drag&drop an article in the sidebar
 * @param {MaybeIterable<Node> | string | null | undefined | false} from Hoot Dom target
 * @param {MaybeIterable<Node> | string | null | undefined | false} to Hoot Dom target
 */
export const dragAndDropArticle = (source, target) => {
    const elementOffset = getOffset(source);
    const targetOffset = getOffset(target);
    // If the target is under the element, the cursor needs to be in the upper
    // part of the target to trigger the move. If it is above, the cursor needs
    // to be in the bottom part.
    const targetY =
        targetOffset.top + (targetOffset.top > elementOffset.top ? target.offsetHeight - 1 : 0);

    const element = source.closest("li");
    element.dispatchEvent(
        new PointerEvent("pointerdown", {
            bubbles: true,
            which: 1,
            clientX: elementOffset.right,
            clientY: elementOffset.top,
        })
    );

    // Initial movement starting the drag sequence
    element.dispatchEvent(
        new PointerEvent("pointermove", {
            bubbles: true,
            which: 1,
            clientX: elementOffset.right,
            clientY: elementOffset.top + SORTABLE_TOLERANCE,
        })
    );

    // Timeouts because sidebar onMove is debounced
    setTimeout(() => {
        target.dispatchEvent(
            new PointerEvent("pointermove", {
                bubbles: true,
                which: 1,
                clientX: targetOffset.right,
                clientY: targetY,
            })
        );

        setTimeout(() => {
            element.dispatchEvent(
                new PointerEvent("pointerup", {
                    bubbles: true,
                    which: 1,
                    clientX: targetOffset.right,
                    clientY: targetY,
                })
            );
        }, 200);
    }, 200);
};

/**
 * WARNING: This method uses the new editor powerBox.
 *
 * Steps to insert an articleLink for the given article, in the first editable
 * html_field found in the given container selector (should have a paragraph
 * as its last element, and the link will be inserted at the position at index
 * offset in the paragraph).
 *
 * @param {string} htmlFieldContainerSelector jquery selector for the container
 * @param {string} articleName name of the article to insert a link for
 * @param {integer} previousSiblingSelector jquery selector for the previous sibling of the article link
 * @returns {Array} tour steps
 */
export function appendArticleLink(htmlFieldContainerSelector, articleName, previousSiblingSelector = "") {
    return [{ // open the command bar
        trigger: `${htmlFieldContainerSelector} .odoo-editor-editable > p:last ${previousSiblingSelector}, ${htmlFieldContainerSelector} .odoo-editor-editable > div.o-paragraph:last ${previousSiblingSelector}`,
        run: function () {
            if (previousSiblingSelector) {
                openPowerbox(this.anchor.parentElement, this.anchor);
            } else {
                openPowerbox(this.anchor);
            }
        },
    }, { // click on the /article command
        trigger: '.o-we-powerbox .o-we-command .o-we-command-img.fa-newspaper-o',
        run: 'click',
    }, {
        trigger: ".o_article_search_input input",
        run: `edit ${articleName}`,
    }, {
        trigger: `.o_article_search_item .o_article_search_name:contains(${articleName})`,
        run: 'click',
    }]
}

/**
 * Ensure that the tour does not end on the Knowledge form view by returning to
 * the home menu.
 */
export function endKnowledgeTour() {
    return [
        ...stepUtils.toggleHomeMenu(),
        {
            trigger: '.o_app[data-menu-xmlid="knowledge.knowledge_menu_root"]',
        }
    ];
}

/**
 * WARNING: uses the legacy editor powerbox.
 *
 * Opens the power box of the editor
 * @param {HTMLElement} paragraph
 * @param {integer} offset position of the command call in the paragraph
 */
export function openCommandBar(paragraph, offset=0) {
    const sel = document.getSelection();
    sel.removeAllRanges();
    const range = document.createRange();
    range.setStart(paragraph, offset);
    range.setEnd(paragraph, offset);
    sel.addRange(range);
    paragraph.dispatchEvent(
        new KeyboardEvent("keydown", {
            key: "/",
        })
    );
    const slash = document.createTextNode("/");
    paragraph.prepend(slash);
    sel.removeAllRanges();
    range.setStart(slash, 1);
    range.setEnd(slash, 1);
    sel.addRange(range);
    paragraph.dispatchEvent(
        new InputEvent("input", {
            inputType: "insertText",
            data: "/",
            bubbles: true,
        })
    );
    paragraph.dispatchEvent(
        new KeyboardEvent("keyup", {
            key: "/",
        })
    );
}

/**
 * WARNING: uses the new editor powerbox.
 *
 * Opens the power box of the editor
 * @param {HTMLElement} paragraph
 * @param {Node} previousSibling previous sibling of the inserted element
 */
export function openPowerbox(paragraph, previousSibling) {
    let offset = 0;
    if (previousSibling) {
        offset = childNodeIndex(previousSibling) + 1;
    }
    const sel = document.getSelection();
    sel.removeAllRanges();
    const range = document.createRange();
    range.setStart(paragraph, offset);
    range.setEnd(paragraph, offset);
    sel.addRange(range);
    paragraph.dispatchEvent(
        new InputEvent("input", {
            inputType: "insertText",
            data: "/",
            bubbles: true,
        })
    );
}

export class WithoutLazyLoading extends Component {
    static template = xml`<t t-slot="default"/>`;
    static props = ["*"];
}

export function embeddedViewPatchFunctions() {
    let unpatchEmbeddedView;
    return {
        before: () => {
            unpatchEmbeddedView = patch(ReadonlyEmbeddedViewComponent.components, {
                ...ReadonlyEmbeddedViewComponent.components,
                WithLazyLoading: WithoutLazyLoading,
            });
        },
        after: () => {
            unpatchEmbeddedView();
        },
    };
}
