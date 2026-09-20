import { leftPos, rightPos } from "@html_editor/utils/position";
import { isContentEditable } from "@html_editor/utils/dom_info";
import { TablePlugin as _TablePlugin } from "@html_editor/main/table/table_plugin";
import { QWebPlugin as _QWebPlugin } from "@html_editor/others/qweb_plugin";
import { closestElement } from "@html_editor/utils/dom_traversal";
import { ToolbarPlugin as _ToolbarPlugin } from "@html_editor/main/toolbar/toolbar_plugin";
import { visitNode } from "../../utils";

function extendLists(...args) {
    return args.flat().filter(Boolean);
}

export class TablePlugin extends _TablePlugin {
    _insertTable() {
        const table = super._insertTable(...arguments);
        if (closestElement(table, "[t-call='web.external_layout']")) {
            table.removeAttribute("class");
            table.classList.add("table", "o_table", "table-borderless");
        }
        return table;
    }
}

const QWEB_STYLING = ["class", "style"].map((attr) => [`t-att-${attr}`, `t-attf-${attr}`]).flat();
const QWEB_T_OUT = ["t-field", "t-out", "t-esc"];

export class QWebPlugin extends _QWebPlugin {
    static shared = ["normalizeExpressions"];

    resources = {
        ...this.resources,
        selectionchange_handlers: extendLists(
            this.resources.selectionchange_handlers,
            this.fullExpressionSelectionChanged.bind(this)
        ),
        clipboard_content_processors: extendLists(
            this.resources.clipboard_content_processors,
            this.cleanExpressionsForCopy.bind(this)
        ),
        normalize_handlers: extendLists(
            this.resources.normalize_handlers,
            this.normalizeExpressions.bind(this)
        ),
        clean_for_save_handlers: extendLists(
            this.resources.clean_for_save_handlers,
            this.cleanExpressionsForSave.bind(this)
        ),
    };

    onClick(ev) {
        if (ev.detail === 1) {
            /* simple click */ if (this.setFullSelection(ev.srcElement)) {
                return;
            }
        }
        super.onClick(ev);
    }

    DUMMY_CONTENT_ATTRS = ["data-oe-demo", "data-oe-expression-readable"];

    normalizeExpressions(node) {
        const doc = this.document;
        visitNode(node, (el) => {
            if (!QWEB_T_OUT.some((att) => el.hasAttribute(att))) {
                return true;
            }

            for (const dummyAttr of this.DUMMY_CONTENT_ATTRS) {
                if (!el.textContent.trim() && el.hasAttribute(dummyAttr)) {
                    el.appendChild(doc.createTextNode(el.getAttribute(dummyAttr)));
                }
            }
            return false;
        });
    }

    cleanExpressionsForCopy(node) {
        Array.from(node.querySelectorAll("[data-oe-expression-readable],[data-oe-demo]")).forEach(
            (el) => {
                if (QWEB_T_OUT.some((attr) => el.hasAttribute(attr))) {
                    el.replaceChildren();
                }
            }
        );
    }

    cleanExpressionsForSave({ root }) {
        visitNode(root, (el) => {
            let doChildren = true;
            for (const dummyAttr of this.DUMMY_CONTENT_ATTRS) {
                if (el.hasAttribute(dummyAttr)) {
                    if (el.textContent.trim() === el.getAttribute(dummyAttr)) {
                        el.replaceChildren();
                    }
                    doChildren = false;
                }
            }
            return doChildren;
        });
    }

    fullExpressionSelectionChanged(selectionData) {
        const selection = selectionData.documentSelection;
        if (!selection) {
            return;
        }
        const node = selection.anchorNode;
        const parent = closestElement(node, "[data-oe-expression-readable]");
        if (parent && parent !== node) {
            this.setFullSelection(parent);
        }
    }

    setFullSelection(qwebNode) {
        if (
            qwebNode.getAttribute("data-oe-expression-readable") &&
            !isContentEditable(qwebNode) &&
            this.editable.contains(qwebNode)
        ) {
            const [anchorNode, anchorOffset] = leftPos(qwebNode);
            const [focusNode, focusOffset] = rightPos(qwebNode);
            this.dependencies.selection.setSelection({
                anchorNode,
                anchorOffset,
                focusNode,
                focusOffset,
            });
            return true;
        }
        return false;
    }
}

export class ToolbarPlugin extends _ToolbarPlugin {
    getButtons() {
        const IDS = [
            "forecolor",
            "backcolor",
            "bold",
            "italic",
            "underline",
            "strikethrough",
            "remove_format",
            "font",
            "font-size",
            "font-family",
            "link",
        ];
        const buttons = super.getButtons(arguments);
        for (const btn of buttons) {
            if (IDS.includes(btn.id)) {
                const originIsDisabled = btn.isDisabled;
                btn.isDisabled = (...args) =>
                    originIsDisabled?.(...args) || this.isButtonDisabled(...args);
            }
        }
        return buttons;
    }

    isButtonDisabled(sel, targetedNodes) {
        return targetedNodes.some(
            (el) =>
                el.nodeType === Node.ELEMENT_NODE &&
                QWEB_STYLING.some((att) => el.hasAttribute(att))
        );
    }
}
