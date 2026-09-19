import { KanbanCompiler } from "@web/views/kanban/kanban_compiler";
import { append, createElement } from "@web/core/utils/xml";
import { evaluateExpr } from "@web/core/py_js/py";

export class PayRunKanbanCompiler extends KanbanCompiler {
    setup() {
        super.setup();
        this.compilers.push({ selector: "[t-name='menu']", fn: this.compileMenu });
    }

    getVisibleExpr(child, params) {
        const invisible = child.getAttribute("invisible");
        if (!params.compileInvisibleNodes && (invisible === "True" || invisible === "1")) {
            return false;
        }
        if (!invisible || invisible === "False" || invisible === "0") {
            return "true";
        } else if (invisible === "True" || invisible === "1") {
            return "false";
        } else {
            return `!__comp__.evaluateBooleanExpr(${JSON.stringify(
                invisible
            )},__comp__.props.record.evalContextWithVirtualIds)`;
        }
    }

    //-----------------------------------------------------------------------------
    // Compilers
    //-----------------------------------------------------------------------------

    /**
     * @param {Element} el
     * @param {Record<string, any>} params
     * @returns {Element}
     */
    compileMenu(el, params) {
        if (!el.children.length) {
            return this.compileGenericNode(el, params);
        }

        const buttonBox = createElement("PayRunButtonBox");
        let slotId = 0;
        for (const child of el.children) {
            const options = evaluateExpr(child.getAttribute("options") || "{}");
            const mainSlot = createElement("t", {
                "t-set-slot": `slot_${slotId++}`,
                isVisible: this.getVisibleExpr(child, params),
                isSmartButton: JSON.stringify(options?.is_smart_button),
                isPriority: JSON.stringify(options?.is_priority),
            });
            child.classList.add("border-0", "flex-grow-1", "oe_stat_button");
            append(mainSlot, this.compileNode(child, params, false));
            append(buttonBox, mainSlot);
        }
        return buttonBox;
    }
}
