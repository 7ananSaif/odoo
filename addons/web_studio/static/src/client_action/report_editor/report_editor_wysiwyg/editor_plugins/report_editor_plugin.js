import { _t } from "@web/core/l10n/translation";
import { sortBy } from "@web/core/utils/arrays";

import { Plugin } from "@html_editor/plugin";
import { closestElement } from "@html_editor/utils/dom_traversal";
import { withSequence } from "@html_editor/utils/resource";
import { MAIN_PLUGINS } from "@html_editor/plugin_sets";
import { nodeSize } from "@html_editor/utils/position";
import { isHtmlContentSupported } from "@html_editor/core/selection_plugin";

import { StudioDynamicPlaceholderPopover } from "./studio_dynamic_placeholder_popover";
import { visitNode } from "../../utils";
import { QWebPlugin, TablePlugin, ToolbarPlugin } from "./editor_plugins";
import { QWebTablePlugin } from "./qweb_table_plugin";

/**
 * @typedef {Object} QwebVariableInfo
 * @property {string} model - The technical model name (e.g. "res.partner").
 * @property {string} name - The human-readable model name.
 * @property {boolean} in_foreach - Whether the variable appears inside a `t-foreach`.
 */

/**
 * @typedef {Record<string, QwebVariableInfo>} AvailableQwebVariables
 */

export class ReportEditorPlugin extends Plugin {
    static id = "report_editor_main";
    static dependencies = ["selection", "history", "overlay", "dom", QWebPlugin.id];

    resources = {
        handleNewRecords: this.handleMutations.bind(this),
        unsplittable_node_predicates: (node) =>
            node.nodeType === Node.ELEMENT_NODE && node.matches(".page, .header, .footer"),
        toolbar_groups: withSequence(9, { id: "report_editor" }),
        toolbar_items: [
            {
                id: "editDynamicField",
                groupId: "report_editor",
                namespaces: ["compact", "expanded"],
                commandId: "editDynamicField",
            },
        ],
        user_commands: [
            {
                id: "insertField",
                title: _t("Field"),
                description: _t("Insert a field"),
                icon: "fa-magic",
                run: this.insertField.bind(this),
                isAvailable: this.isInsertAvailable.bind(this),
            },
            {
                id: "insertDynamicTable",
                title: _t("Dynamic Table"),
                description: _t("Insert a table based on a relational field."),
                icon: "fa-magic",
                run: this.insertTableX2Many.bind(this),
                isAvailable: this.isInsertAvailable.bind(this),
            },
            {
                id: "editDynamicField",
                title: _t("Edit field"),
                description: _t("Change the placeholder or the expression for an existing field"),
                icon: "fa-pencil",
                run: this.editTField.bind(this),
                isAvailable: () => !!this.getTargetedTField(),
            },
        ],
        powerbox_categories: withSequence(1, {
            id: "report_tools",
            name: _t("Report Tools"),
        }),
        powerbox_items: [
            withSequence(20, {
                categoryId: "report_tools",
                commandId: "insertField",
            }),
            withSequence(25, {
                categoryId: "report_tools",
                commandId: "insertDynamicTable",
            }),
        ],
    };

    CUSTOM_BRANDING_ATTR = [
        "ws-view-id",
        "ws-call-key",
        "ws-call-group-key",
        "ws-real-children",
        "o-diff-key",
    ];

    setup() {
        this.fieldPopover = this.dependencies.overlay.createOverlay(
            StudioDynamicPlaceholderPopover,
            {
                hasAutofocus: true,
                editable: this.editable,
                className: "bg-light",
            }
        );
    }

    isInsertAvailable(selection) {
        if (!isHtmlContentSupported(selection)) {
            return;
        }
        const { availableQwebVariables, initialQwebVar, isEditingFooterHeader } =
            this.getQwebVariables(this.getPopoverAnchor(selection));

        return !!this.getDefaultVariable(
            initialQwebVar,
            availableQwebVariables,
            isEditingFooterHeader
        );
    }

    getPopoverAnchor(selection) {
        selection ||= this.dependencies.selection.getEditableSelection();
        const { anchorNode } = selection;
        return anchorNode.nodeType === Node.ELEMENT_NODE ? anchorNode : anchorNode.parentElement;
    }

    getTargetedTField() {
        const elements = this.dependencies.selection
            .getTargetedNodes()
            .filter((n) => n.nodeType === Node.ELEMENT_NODE);

        if (elements.length === 1 && elements[0].hasAttribute("t-field")) {
            // For now, ban expressions that contain a parenthesis
            // That would be a function call (usually sudo)
            // but we are *really* not sure about this.
            if (elements[0].getAttribute("t-field").includes("(")) {
                return;
            }
            return elements[0];
        }
    }

    async editTField() {
        const tfield = this.getTargetedTField();
        if (!tfield) {
            return;
        }
        const popoverAnchor = tfield;
        const {
            availableQwebVariables,
            initialQwebVar: defaultQwebVar,
            isEditingFooterHeader,
        } = this.getQwebVariables(popoverAnchor);

        let initialPath = popoverAnchor.getAttribute("t-field").split(".");
        let initialQwebVar = initialPath[0];
        initialPath = initialPath.slice(1).join(".");
        let resModel = availableQwebVariables[initialQwebVar]?.model;
        if (!resModel) {
            resModel = this.config.reportResModel;
            initialQwebVar = this.getDefaultVariable(
                defaultQwebVar,
                availableQwebVariables,
                isEditingFooterHeader
            );
            initialPath = false;
        }

        const initialLabelValue =
            popoverAnchor.innerText ||
            popoverAnchor.getAttribute("data-oe-demo") ||
            popoverAnchor.getAttribute("data-oe-expression-readable") ||
            false;
        await this.fieldPopover.open({
            target: popoverAnchor,
            props: {
                close: () => this.fieldPopover.close(),
                availableQwebVariables,
                initialQwebVar,
                resModel,
                initialPath,
                initialLabelValue,
                showOnlyX2ManyFields: false,
                validate: (
                    qwebVar,
                    fieldNameChain,
                    defaultValue = "",
                    is_image,
                    relation,
                    fieldString
                ) => {
                    let isDirty = false;
                    if (qwebVar !== initialQwebVar || initialPath !== fieldNameChain) {
                        isDirty = true;
                        popoverAnchor.setAttribute(
                            "data-oe-expression-readable",
                            fieldString || `field: "${qwebVar}.${fieldNameChain}"`
                        );
                        popoverAnchor.setAttribute("t-field", `${qwebVar}.${fieldNameChain}`);
                        if (odoo.debug) {
                            popoverAnchor.setAttribute("title", `${qwebVar}.${fieldNameChain}`);
                        }

                        if (is_image) {
                            popoverAnchor.setAttribute("t-options-widget", "'image'");
                            popoverAnchor.setAttribute("t-options-qweb_img_raw_data", 1);
                        } else {
                            popoverAnchor.removeAttribute("t-options-widget"),
                                popoverAnchor.removeAttribute("t-options-qweb_img_raw_data");
                        }
                    }
                    if (initialLabelValue !== defaultValue) {
                        isDirty = true;
                        popoverAnchor.setAttribute("data-oe-demo", defaultValue);
                        const prevText = popoverAnchor.textContent;
                        this.dependencies.history.applyCustomMutation({
                            apply: () => {
                                popoverAnchor.textContent = "";
                                this.dependencies.qweb.normalizeExpressions(popoverAnchor);
                                const parentView = popoverAnchor.closest(`[ws-view-id]`);
                                if (!parentView.classList.contains("o_dirty")) {
                                    parentView.classList.add("o_dirty");
                                }
                            },
                            revert: () => {
                                popoverAnchor.textContent = prevText;
                            },
                        });
                    }

                    if (isDirty) {
                        this.dependencies.history.addStep();
                    }
                },
            },
        });
    }

    /**
     * @param {HTMLElement} element
     * @return {{isEditingFooterHeader: boolean, availableQwebVariables: AvailableQwebVariables, initialQwebVar: string} | {}}
     */
    getQwebVariables(element) {
        if (!element) {
            return {};
        }
        const nodeOeContext = element.closest("[oe-context]");
        let availableQwebVariables =
            (nodeOeContext && JSON.parse(nodeOeContext.getAttribute("oe-context"))) || {};

        const isEditingFooterHeader = !!closestElement(element, ".header,.footer");
        let initialQwebVar;
        if (isEditingFooterHeader) {
            const companyVars = Object.entries(availableQwebVariables).filter(
                ([k, v]) => v.model === "res.company"
            );
            initialQwebVar = companyVars[0]?.[0];
            availableQwebVariables = Object.fromEntries(companyVars);
        } else {
            initialQwebVar = this.getOrderedTAs(element)[0] || "";
        }
        return {
            isEditingFooterHeader,
            availableQwebVariables,
            initialQwebVar,
        };
    }

    /**
     * @param {AvailableQwebVariables} availableQwebVariables
     * @param {boolean} isEditingFooterHeader
     * @param {string} resModel
     * @return {{label: string, value: string}[]}
     */
    sortedVariables(availableQwebVariables, isEditingFooterHeader, resModel) {
        const entries = Object.entries(availableQwebVariables).filter(
            ([k, v]) => v.in_foreach && !isEditingFooterHeader
        );
        const sortFn = ([k, v]) => {
            let score = 0;
            if (k === "doc") {
                score += 2;
            }
            if (k === "docs") {
                score -= 2;
            }
            if (k === "o") {
                score++;
            }
            if (v.model === resModel) {
                score++;
            }
            return score;
        };

        const mapFn = ([k, v]) => ({
            value: k,
            label: `${k} (${v.name})`,
        });
        return sortBy(entries, sortFn, "desc").map((e) => mapFn(e));
    }

    /**
     * @param {string} [initialQwebVar]
     * @param {AvailableQwebVariables} availableQwebVariables
     * @param {boolean} isEditingFooterHeader
     * @return {string|undefined}
     */
    getDefaultVariable(initialQwebVar, availableQwebVariables, isEditingFooterHeader) {
        if (initialQwebVar && initialQwebVar in availableQwebVariables) {
            return initialQwebVar;
        }
        if (isEditingFooterHeader) {
            const companyVar = Object.entries(availableQwebVariables).find(
                ([k, v]) => v.model === "res.company"
            );
            return companyVar && companyVar[0];
        }
        const resModel = this.config.reportResModel;
        const sortedVariables = this.sortedVariables(
            availableQwebVariables,
            isEditingFooterHeader,
            resModel
        );

        let defaultVar = sortedVariables.find((v) => {
            return ["doc", "o"].includes(v.value);
        });
        defaultVar ??= sortedVariables.find(
            (v) => availableQwebVariables[v.value].model === resModel
        );
        return defaultVar && defaultVar.value;
    }

    getOrderedTAs(node) {
        const results = [];
        while (node) {
            const closest = node.closest("[t-foreach]");
            if (closest) {
                results.push(closest.getAttribute("t-as"));
                node = closest.parentElement;
            } else {
                node = null;
            }
        }
        return results;
    }

    async insertTableX2Many() {
        const { popoverAnchor, props } = this.getFieldPopoverParams();
        await this.fieldPopover.open({
            target: popoverAnchor,
            props: {
                ...props,
                showOnlyX2ManyFields: true,
                validate: (
                    qwebVar,
                    fieldNameChain,
                    defaultValue = "",
                    is_image,
                    relation,
                    relationName
                ) => {
                    const doc = this.document;
                    doc.defaultView.focus();

                    const table = doc.createElement("table");
                    table.classList.add("table", "table-sm");

                    const tBody = table.createTBody();

                    const topRow = tBody.insertRow();
                    topRow.classList.add(
                        "border-bottom",
                        "border-top-0",
                        "border-start-0",
                        "border-end-0",
                        "border-2",
                        "border-dark",
                        "fw-bold"
                    );
                    const topTd = doc.createElement("td");
                    topTd.appendChild(doc.createTextNode(defaultValue || "Column name"));
                    topRow.appendChild(topTd);

                    const tr = doc.createElement("tr");
                    tr.setAttribute("t-foreach", `${qwebVar}.${fieldNameChain}`);
                    tr.setAttribute("t-as", "x2many_record");
                    tr.setAttribute(
                        "oe-context",
                        JSON.stringify({
                            x2many_record: {
                                model: relation,
                                in_foreach: true,
                                name: relationName,
                            },
                            ...props.availableQwebVariables,
                        })
                    );
                    tBody.appendChild(tr);

                    const td = doc.createElement("td");
                    td.textContent = _t("Insert a field...");
                    tr.appendChild(td);

                    this.dependencies.dom.insert(table);
                    this.dependencies.selection.setSelection({
                        anchorNode: td,
                        focusOffset: nodeSize(td),
                    });
                    this.dependencies.history.addStep();
                },
            },
        });
    }

    async insertField() {
        const { popoverAnchor, props } = this.getFieldPopoverParams();
        await this.fieldPopover.open({
            target: popoverAnchor,
            props: {
                ...props,
                showOnlyX2ManyFields: false,
                validate: (
                    qwebVar,
                    fieldNameChain,
                    defaultValue = "",
                    is_image,
                    relation,
                    fieldString
                ) => {
                    const doc = this.document;
                    doc.defaultView.focus();

                    const span = doc.createElement("span");
                    span.setAttribute(
                        "data-oe-expression-readable",
                        fieldString || `field: "${qwebVar}.${fieldNameChain}"`
                    );
                    span.setAttribute("data-oe-demo", defaultValue);
                    span.setAttribute("t-field", `${qwebVar}.${fieldNameChain}`);

                    if (odoo.debug) {
                        span.setAttribute("title", `${qwebVar}.${fieldNameChain}`);
                    }

                    if (is_image) {
                        span.setAttribute("t-options-widget", "'image'");
                        span.setAttribute("t-options-qweb_img_raw_data", 1);
                    }
                    this.dependencies.dom.insert(span);
                    this.dependencies.history.addStep();
                },
            },
        });
    }

    getFieldPopoverParams() {
        const resModel = this.config.reportResModel;
        const popoverAnchor = this.getPopoverAnchor();
        const { availableQwebVariables, initialQwebVar, isEditingFooterHeader } =
            this.getQwebVariables(popoverAnchor);
        const defaultVariable = this.getDefaultVariable(
            initialQwebVar,
            availableQwebVariables,
            isEditingFooterHeader
        );
        return {
            popoverAnchor,
            props: {
                close: () => this.fieldPopover.close(),
                availableQwebVariables,
                initialQwebVar: defaultVariable,
                resModel,
            },
        };
    }

    /**
     * @param {import("@html_editor/core/history_plugin").HistoryMutationRecord[]} records
     */
    handleMutations(records) {
        for (const record of records) {
            if (record.type === "attributes") {
                if (record.attributeName === "contenteditable") {
                    continue;
                }
                if (record.attributeName.startsWith("data-oe-t")) {
                    continue;
                }
            }
            if (record.type === "childList") {
                record.addedTrees
                    .map((tree) => tree.node)
                    .forEach((el) => {
                        if (el.nodeType !== 1) {
                            return;
                        }
                        visitNode(el, (node) => {
                            this.CUSTOM_BRANDING_ATTR.forEach((attr) => {
                                node.removeAttribute(attr);
                            });
                            node.classList.remove("o_dirty");
                        });
                    });
                const realRemoved = record.removedTrees
                    .map((tree) => tree.node)
                    .filter((n) => n.nodeType !== Node.COMMENT_NODE);
                if (!realRemoved.length && !record.addedTrees.length) {
                    continue;
                }
            }

            let target = record.target;
            if (!target.isConnected) {
                continue;
            }
            if (target.nodeType !== Node.ELEMENT_NODE) {
                target = target.parentElement;
            }
            if (!target) {
                continue;
            }

            target = target.closest(`[ws-view-id]`);
            if (!target) {
                continue;
            }
            if (!target.classList.contains("o_dirty")) {
                target.classList.add("o_dirty");
            }
        }
    }
}

const REPORT_EDITOR_PLUGINS_MAP = Object.fromEntries(MAIN_PLUGINS.map((cls) => [cls.id, cls]));
Object.assign(REPORT_EDITOR_PLUGINS_MAP, {
    [QWebPlugin.id]: QWebPlugin,
    [QWebTablePlugin.id]: QWebTablePlugin,
    [TablePlugin.id]: TablePlugin,
    [ToolbarPlugin.id]: ToolbarPlugin,
    [ReportEditorPlugin.id]: ReportEditorPlugin,
});

export function getReportEditorPlugins() {
    return Object.values(REPORT_EDITOR_PLUGINS_MAP);
}
