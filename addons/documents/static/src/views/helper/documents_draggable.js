import { markup } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { DRAGGED_CLASS } from "@web/core/utils/draggable_hook_builder";
import { makeDraggableHook } from "@web/core/utils/draggable_hook_builder_owl";
import { createDocumentFragmentFromContent } from "@web/core/utils/html";
import { closestScrollableX, closestScrollableY } from "@web/core/utils/scrolling";

export const useDraggableDocuments = makeDraggableHook({
    name: "useDraggableDocuments",
    acceptedParams: {
        model: [Object],
        targetSelector: [String],
    },

    onComputeParams({ ctx, params }) {
        ctx.model = params.model;
        ctx.targetSelector = params.targetSelector;
        ctx.edgeScrolling.force = true;
        ctx.followCursor = false;
    },

    onWillStartDrag() {
        this.tempDraggedElements = [];
        this.initialPositions = [];
        this.lastDragTime = 0;
        this.isInvalidTarget = false;
    },

    onDragStart({ ctx, callHandler, addClass, addCleanup, addStyle, addListener, removeClass }) {
        const { current, model, ref, targetSelector } = ctx;
        const { element } = current;
        addClass(ref.el, "o_documents_dragging");
        removeClass(element, DRAGGED_CLASS);
        const searchPanelEl = document.querySelector(".o_documents_search_panel");
        const currentElementId = parseInt(element.dataset.valueId);

        // Reinitialize the selection if drag action is on an unselected document
        if (
            !model.root.selection.length ||
            !model.root.selection.map((r) => r.data.id).includes(currentElementId)
        ) {
            model.root.selection.forEach((r) => (r.selected = false));
            model.root.records.find((r) => r.data.id === currentElementId).selected = true;
        }
        this._setDraggedRecords(model);

        const recordData = model.root.records.find((r) => r.data.id === currentElementId).data;
        current.dragMessageText = recordData.display_name;
        current.dragMessage = this._createDnDElement(recordData, model.root.selection.length);
        ref.el.append(current.dragMessage);

        const allElements = ref.el.classList.contains("o_kanban_renderer")
            ? ref.el.querySelectorAll(".o_kanban_record:not(.o_kanban_ghost)")
            : ref.el.querySelectorAll(".o_data_row");
        this.selectedElements = Array.from(allElements).filter((el) =>
            this.draggedRecords.all.includes(parseInt(el.dataset.valueId))
        );
        for (const selectedEl of this.selectedElements) {
            const sourceRect = selectedEl.getBoundingClientRect();
            const sourceName = model.root.records.find(
                (r) => r.data.id === parseInt(selectedEl.dataset.valueId)
            ).data.name;
            this.initialPositions.push({
                initialTop: sourceRect.top,
                initialLeft: sourceRect.left,
            });

            const tempEl = document.createElement("div");
            tempEl.innerText = sourceName;
            tempEl.classList.add("o_record_temporary");
            this.tempDraggedElements.push(tempEl);
            document.body.append(tempEl);
            addCleanup(() => tempEl.remove());

            tempEl.style.left = `${sourceRect.left}px`;
            tempEl.style.top = `${sourceRect.top}px`;

            addStyle(selectedEl, { opacity: 0.3 });
        }
        addStyle(current.dragMessage, { opacity: 1 });
        setTimeout(() => {
            this.tempDraggedElements.forEach((temp) => temp.remove());
            this.tempDraggedElements = [];
        }, 250);

        const switchContainer = (container) => {
            current.container = container;
            [current.scrollParentX, current.scrollParentY] = [
                closestScrollableX(container),
                closestScrollableY(container),
            ];
        };

        // Search Panel Event Handlers
        const onSearchPanelFolderPointerOver = (ev) => {
            const targetClasses = ev.target.classList;
            if (
                targetClasses.contains("o_search_panel_label") ||
                targetClasses.contains("o_search_panel_label_title") ||
                targetClasses.contains("w-100")
            ) {
                const valueEl = ev.target.closest(".o_search_panel_category_value");
                const targetFolder = model.env.searchModel.getFolderById(
                    parseInt(valueEl.dataset.valueId) || valueEl.dataset.valueId
                );
                this._checkTargetValidity(
                    targetFolder,
                    model,
                    current.dragMessage,
                    current.dragMessageText,
                    true
                );
                if (!ev.ctrlKey) {
                    ref.el.classList.remove("o_documents_dnd_shortcut");
                }

                const allSelected = searchPanelEl.querySelectorAll(":scope .o_drag_over_selector");
                for (const selected of allSelected) {
                    selected.classList.remove("o_drag_over_selector");
                }
                addClass(valueEl, "o_drag_over_selector");
                if (!this.isInvalidTarget) {
                    model.env.documentsView.bus.trigger("documents-expand-folder", {
                        folderId: targetFolder.id,
                    });
                }
            }
        };

        const onSearchPanelFolderPointerEnter = (ev) => {
            switchContainer(searchPanelEl);
        };

        const onSearchPanelFolderPointerLeave = (ev) => {
            switchContainer(ref.el);
            if (this.isInvalidTarget) {
                this.isInvalidTarget = false;
                this._resetDragMessage(current.dragMessage, current.dragMessageText);
            }
            const allSelected = searchPanelEl.querySelectorAll(":scope .o_drag_over_selector");
            for (const selected of allSelected) {
                selected.classList.remove("o_drag_over_selector");
            }
        };

        // Target Folders Event Handlers
        const onTargetFolderPointerEnter = (ev) => {
            const targetFolder = model.env.searchModel.getFolderById(
                parseInt(ev.currentTarget.dataset.valueId) || ev.currentTarget.dataset.valueId
            );
            this._checkTargetValidity(
                targetFolder,
                model,
                current.dragMessage,
                current.dragMessageText
            );

            callHandler("onTargetPointerEnter", {
                target: ev.currentTarget,
                isInvalid: this.isInvalidTarget,
            });
        };

        const onTargetFolderPointerLeave = (ev) => {
            if (this.isInvalidTarget) {
                this.isInvalidTarget = false;
                this._resetDragMessage(current.dragMessage, current.dragMessageText);
            }
            callHandler("onTargetPointerLeave", { target: ev.currentTarget });
        };

        for (const targetFolder of ref.el.querySelectorAll(targetSelector)) {
            addListener(targetFolder, "pointerenter", onTargetFolderPointerEnter);
            addListener(targetFolder, "pointerleave", onTargetFolderPointerLeave);
        }
        addListener(searchPanelEl, "pointerover", onSearchPanelFolderPointerOver);
        addListener(searchPanelEl, "pointerenter", onSearchPanelFolderPointerEnter);
        addListener(searchPanelEl, "pointerleave", onSearchPanelFolderPointerLeave);

        this._updateDragInfoPosition(ctx, addStyle);

        addCleanup(() => {
            current.dragMessage.remove();
        });
    },

    onDrag({ ctx, addStyle }) {
        this._updateDragInfoPosition(ctx, addStyle);
        if (this.tempDraggedElements.length) {
            const now = Date.now();
            if (now - this.lastDragTime >= 50) {
                this.lastDragTime = now;
                this._updateTempElementsAnimation(ctx);
            }
        }
    },

    async onDrop({ ctx, target }) {
        const { model, ref } = ctx;

        if (this.isInvalidTarget) {
            return;
        }
        const targetElement =
            target.closest(".o_search_panel_category_value") ||
            target.closest(".o_kanban_record") ||
            target.closest(".o_data_row");
        if (!targetElement) {
            return;
        }
        if (targetElement.dataset.valueId === "TRASH") {
            if (
                this.draggedRecords.movableRecordIds.length &&
                (await model.documentService.moveToTrash(this.draggedRecords.movableRecordIds))
            ) {
                model.notification.add(
                    _t(
                        "%s document(s) sent to trash.",
                        this.draggedRecords.movableRecordIds.length
                    ),
                    { type: "success" }
                );
            }
            model.env.searchModel._reloadSearchModel(true);
            return;
        }
        const targetFolderId =
            parseInt(targetElement.dataset.valueId) || targetElement.dataset.valueId;
        const sourceFolder = model.env.searchModel.getSelectedFolder();
        const targetFolder = model.env.searchModel.getFolderById(targetFolderId);

        if (sourceFolder === targetFolder) {
            return;
        }

        if (targetFolder.id === "COMPANY") {
            await model.documentService.moveToCompanyRoot(this.draggedRecords);
            model.env.searchModel._reloadSearchModel(true);
            return;
        }

        let expectedAccessRightsChanges = false;
        if (
            !isNaN(targetFolder.id) && // no change for these fields
            this._getMovableRecords(model).some(
                (record) =>
                    record.data.access_internal !== targetFolder.access_internal ||
                    record.data.access_via_link !== targetFolder.access_via_link ||
                    (targetFolder.access_via_link !== "none" &&
                        record.data.is_access_via_link_hidden !==
                            targetFolder.is_access_via_link_hidden)
            )
        ) {
            expectedAccessRightsChanges = true;
        }

        await model.documentService.moveOrCreateShortcut(
            this.draggedRecords,
            targetFolder,
            ref.el.classList.contains("o_documents_dnd_shortcut"),
            expectedAccessRightsChanges
        );

        model.load();
        model.notify();
        model.env.searchModel._reloadSearchModel(true);
    },

    _getMovableRecords(model) {
        return model.root.selection.filter(
            (record) => !record.data.lock_uid && record.data.user_permission === "edit"
        );
    },

    _setDraggedRecords(model) {
        this.draggedRecords = {};
        this.draggedRecords.movableRecordIds = this._getMovableRecords(model).map(
            (record) => record.data.id
        );
        this.draggedRecords.nonMovableRecordIds = model.root.selection
            .filter((record) => !this.draggedRecords.movableRecordIds.includes(record.data.id))
            .map((record) => record.data.id);
        this.draggedRecords.all = [
            ...this.draggedRecords.movableRecordIds,
            ...this.draggedRecords.nonMovableRecordIds,
        ];
    },

    _createDnDElement(recordData, documentsCount) {
        const docCountPill =
            documentsCount > 1
                ? markup`<div class="o_documents_dnd_pill bg-success border border-light rounded-circle p-1 text-center">${documentsCount}</div>`
                : "";
        return createDocumentFragmentFromContent(markup`
            <span class="o_documents_dnd o_documents_dnd_info d-flex p-2">
                <i class="o_documents_mimetype_icon o_image" data-mimetype=${recordData.mimetype} title=${recordData.mimetype}></i>
                <span class="o_documents_dnd_text ps-2">${recordData.display_name}</span>
                <div class="o_documents_dnd_pill_container d-flex position-absolute top-0 start-100 translate-middle">
                    <div class="o_documents_dnd_pill o_documents_dnd_modifier bg-info border border-light rounded-circle p-1">
                        <i class="fa fa-external-link-square"></i>
                    </div>
                    ${docCountPill}
                </div>
            </span>
        `).body.firstChild;
    },

    _checkTargetValidity(targetFolder, model, dragMessage, dragMessageText, reset = false) {
        let errorMessage = "";
        if (
            (this.isInvalidTarget = !targetFolder || ["RECENT", "SHARED"].includes(targetFolder.id))
        ) {
            errorMessage = _t(
                "You can't create shortcuts in nor move documents to this special folder."
            );
        } else if (
            (this.isInvalidTarget =
                this.draggedRecords.nonMovableRecordIds.length && targetFolder.id === "TRASH")
        ) {
            errorMessage = _t(
                "There is at least one document you cannot move to trash in your selection."
            );
        } else if (
            (this.isInvalidTarget =
                targetFolder.user_permission !== "edit" &&
                targetFolder.id === "COMPANY" &&
                !model.documentService.userIsDocumentManager)
        ) {
            errorMessage = _t("You don't have the rights to write in this folder.");
        } else if (
            (this.isInvalidTarget = this.draggedRecords.movableRecordIds.some((recordId) =>
                model.env.searchModel
                    .getFolderAndParents(targetFolder)
                    .map((f) => f.id)
                    .includes(recordId)
            ))
        ) {
            errorMessage = _t("You cannot move a folder into itself or a children.");
        }
        if (this.isInvalidTarget) {
            this._setErrorMessage(dragMessage, errorMessage);
        } else if (reset) {
            this._resetDragMessage(dragMessage, dragMessageText);
        }
    },

    _setErrorMessage(dragMessage, errorMessage) {
        dragMessage.classList.remove("o_documents_dnd_info");
        dragMessage.classList.add("alert", "alert-warning");
        dragMessage.querySelector(".o_documents_dnd_text").textContent = errorMessage;
    },

    _resetDragMessage(dragMessage, dragMessageText) {
        dragMessage.classList.remove("alert", "alert-warning");
        dragMessage.classList.add("o_documents_dnd_info");
        dragMessage.querySelector(".o_documents_dnd_text").textContent = dragMessageText;
    },

    _updateDragInfoPosition(ctx, addStyle) {
        const { dragMessage } = ctx.current;
        addStyle(dragMessage, {
            left: `${ctx.pointer.x}px`,
            top: `${ctx.pointer.y}px`,
        });
    },

    _updateTempElementsAnimation(ctx) {
        this.tempDraggedElements.forEach((clone, index) => {
            const { dragMessage } = ctx.current;
            const messageRect = dragMessage.getBoundingClientRect();
            const initialPos = this.initialPositions[index];

            const dx = ctx.pointer.x - initialPos.initialLeft;
            const dy = ctx.pointer.y - initialPos.initialTop;

            clone.style.transform = `translate(${dx}px, ${dy}px)`;
            clone.style.width = `${messageRect.width}px`;
            clone.style.height = `${messageRect.height}px`;
        });
    },
});
