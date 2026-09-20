import { isHtmlContentSupported } from "@html_editor/core/selection_plugin";
import { Plugin } from "@html_editor/plugin";
import {
    baseContainerGlobalSelector,
    getBaseContainerSelector,
} from "@html_editor/utils/base_container";
import { closestElement } from "@html_editor/utils/dom_traversal";
import { withSequence } from "@html_editor/utils/resource";
import { renderToElement } from "@web/core/utils/render";
import { _t } from "@web/core/l10n/translation";

const hostSelector = "[data-embedded='foldableSection']";
const titleSelector = "[data-embedded-editable='title']";
const contentSelector = "[data-embedded-editable='content']";

export class FoldableSectionPlugin extends Plugin {
    static id = "foldableSection";
    static dependencies = ["baseContainer", "history", "selection", "dom"];
    resources = {
        hints: [
            withSequence(10, {
                selector: `${hostSelector} ${titleSelector} > ${baseContainerGlobalSelector}`,
                text: _t("Add a title to your section"),
            }),
            withSequence(10, {
                selector: `${hostSelector} ${contentSelector}:not(:focus) > ${baseContainerGlobalSelector}:only-child`,
                text: _t("Type something inside this section"),
            }),
        ],
        move_node_blacklist_selectors: `${hostSelector} ${titleSelector} > ${baseContainerGlobalSelector}`,
        user_commands: [
            {
                id: "addFoldableSection",
                title: _t("Foldable Section"),
                description: _t("Add a foldable section."),
                icon: "fa-bookmark",
                run: () => this.insertFoldableSection(),
                isAvailable: isHtmlContentSupported,
            },
        ],
        powerbox_items: [
            {
                categoryId: "structure",
                commandId: "addFoldableSection",
                isAvailable: (selection) => !closestElement(selection.anchorNode, hostSelector),
            },
        ],
        hint_targets_providers: (selectionData, editable) => [
            ...editable.querySelectorAll(
                `${hostSelector} ${contentSelector} > ${baseContainerGlobalSelector}:only-child`
            ),
        ],
        power_buttons_visibility_predicates: this.showPowerButtons.bind(this),
        split_element_block_overrides: withSequence(1, this.handleSplitElementBlock.bind(this)),
        powerbox_blacklist_selectors: `${hostSelector} ${titleSelector} > ${baseContainerGlobalSelector}`,
    };

    handleSplitElementBlock({ targetNode }) {
        if (closestElement(targetNode, `${hostSelector} ${titleSelector}`)) {
            return true;
        }
    }

    insertFoldableSection() {
        const baseContainer = this.dependencies.baseContainer.createBaseContainer();
        const baseContainerNodeName = baseContainer.nodeName;
        const baseContainerClass = baseContainer.className;
        const baseContainerSelector = getBaseContainerSelector(baseContainerNodeName);
        const foldableSection = renderToElement("knowledge.FoldableSectionBlueprint", {
            baseContainerAttributes: {
                class: baseContainerClass,
            },
            baseContainerNodeName,
            embeddedProps: JSON.stringify({ showContent: true }),
        });
        this.dependencies.dom.insert(foldableSection);
        this.dependencies.selection.setCursorStart(
            foldableSection.querySelector(
                `${hostSelector} ${titleSelector} ${baseContainerSelector}`
            )
        );
        this.dependencies.history.addStep();
    }
    showPowerButtons(selection) {
        return (
            selection.isCollapsed &&
            !closestElement(selection.anchorNode, `${hostSelector} ${titleSelector}`)
        );
    }
}
