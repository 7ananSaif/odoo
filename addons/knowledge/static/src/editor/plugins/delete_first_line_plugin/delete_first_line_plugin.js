import { Plugin } from "@html_editor/plugin";
import {
    isEmptyBlock,
    isParagraphRelatedElement,
    paragraphRelatedElementsSelector,
} from "@html_editor/utils/dom_info";
import { closestBlock } from "@html_editor/utils/blocks";

export class KnowledgeDeleteFirstLinePlugin extends Plugin {
    static id = "deleteFirstLinePlugin";
    static dependencies = ["selection", "history"];
    resources = {
        delete_backward_overrides: this.handleDeleteBackward.bind(this),
    };

    /**
     * Handles the deletion of the 1st line.
     * @param {Range} range
     * @returns
     */
    handleDeleteBackward(range) {
        const { endContainer } = range;
        const endContainerBlock = closestBlock(endContainer);
        if (
            !(isParagraphRelatedElement(endContainerBlock) && isEmptyBlock(endContainerBlock)) ||
            !endContainerBlock.matches(".odoo-editor-editable > *:first-child") ||
            endContainerBlock.matches(":only-child")
        ) {
            return;
        }
        let current = endContainerBlock.nextElementSibling;
        while (current && !current.matches(paragraphRelatedElementsSelector)) {
            current = current.nextElementSibling;
        }
        if (!current) {
            const newParagraph = this.dependencies.baseContainer.createBaseContainer();
            newParagraph.appendChild(this.document.createElement("br"));
            this.editable.append(newParagraph);
            current = newParagraph;
        }
        endContainerBlock.remove();
        this.dependencies.selection.setCursorStart(current);
        return true;
    }
}
