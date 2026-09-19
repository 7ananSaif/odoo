import {
    Component,
    markup,
    onWillRender,
    onWillStart,
    onWillUnmount,
    onWillUpdateProps,
    reactive,
    useEffect,
    useExternalListener,
    useRef,
    useState,
} from "@odoo/owl";
import { hasTouch, isMobileOS } from "@web/core/browser/feature_detection";
import { Domain } from "@web/core/domain";
import { serializeDate, serializeDateTime, toLocaleDateTimeString } from "@web/core/l10n/dates";
import { localization } from "@web/core/l10n/localization";
import { is24HourFormat } from "@web/core/l10n/time";
import { _t } from "@web/core/l10n/translation";
import { usePopover } from "@web/core/popover/popover_hook";
import { evaluateBooleanExpr } from "@web/core/py_js/py";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { zipWith } from "@web/core/utils/arrays";
import { KeepLast } from "@web/core/utils/concurrency";
import { useBus, useService } from "@web/core/utils/hooks";
import { omit, pick } from "@web/core/utils/objects";
import { nbsp } from "@web/core/utils/strings";
import { debounce, throttleForAnimation } from "@web/core/utils/timing";
import { url } from "@web/core/utils/urls";
import { parseXML } from "@web/core/utils/xml";
import { useVirtualGrid } from "@web/core/virtual_grid_hook";
import { extractFieldsFromArchInfo } from "@web/model/relational_model/utils";
import { useCallbackRecorder } from "@web/search/action_hook";
import { formatFloatTime } from "@web/views/fields/formatters";
import { KanbanRecord } from "@web/views/kanban/kanban_record";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";
import { GanttConnector } from "./gantt_connector";
import {
    dateAddFixedOffset,
    diffColumn,
    getBadges,
    getCellColor,
    getCellsOnRow,
    getColorIndex,
    getHoveredCellPart,
    localEndOf,
    localStartOf,
    useGanttConnectorDraggable,
    useGanttDraggable,
    useGanttResizable,
    useGanttSelectable,
    useGanttUndraggable,
    useMultiHover,
} from "./gantt_helpers";
import { GanttMultiSelectionButtons } from "./gantt_multi_selection_buttons";
import { GanttPopover } from "./gantt_popover";
import { GanttRendererControls } from "./gantt_renderer_controls";
import { GanttRowProgressBar } from "./gantt_row_progress_bar";
import { GanttTimeDisplayBadge } from "./gantt_time_display_badge";

const viewRegistry = registry.category("views");

const { DateTime, Interval } = luxon;

/**
 * @typedef {`__connector__${number | "new"}`} ConnectorId
 * @typedef {import("./gantt_connector").ConnectorProps} ConnectorProps
 * @typedef {luxon.DateTime} DateTime
 * @typedef {"copy" | "reschedule"} DragActionMode
 * @typedef {"drag" | "locked" | "resize"} InteractionMode
 * @typedef {`__pill__${number}`} PillId
 * @typedef {import("./gantt_model").RowId} RowId
 *
 * @typedef Column
 * @property {number} index
 * @property {GridPosition} grid
 * @property {boolean} [isToday]
 * @property {DateTime} start
 * @property {DateTime} stop
 *
 * @typedef GridPosition
 * @property {number | number[]} [row]
 * @property {number | number[]} [column]
 *
 * @typedef Group
 * @property {boolean} break
 * @property {number} col
 * @property {Pill[]} pills
 * @property {number} aggregateValue
 * @property {GridPosition} grid
 *
 * @typedef GanttRendererProps
 * @property {import("./gantt_model").GanttModel} model
 * @property {Document} arch
 * @property {string} class
 * @property {(context: Record<string, any>)} create
 * @property {{ content?: Point }} [scrollPosition]
 * @property {{ el: HTMLDivElement | null }} [contentRef]
 *
 * @typedef HoveredInfo
 * @property {Element | null} connector
 * @property {HTMLElement | null} hoverable
 * @property {HTMLElement | null} pill
 *
 * @typedef Interaction
 * @property {InteractionMode | null} mode
 * @property {DragActionMode} dragAction
 *
 * @typedef Pill
 * @property {PillId} id
 * @property {boolean} disableStartResize
 * @property {boolean} disableStopResize
 * @property {number} leftMargin
 * @property {number} level
 * @property {string} name
 * @property {DateTime} startDate
 * @property {DateTime} stopDate
 * @property {GridPosition} grid
 * @property {RelationalRecord} record
 * @property {number} _color
 * @property {number} _progress
 *
 * @typedef Point
 * @property {number} [x]
 * @property {number} [y]
 *
 * @typedef {Record<string, any>} RelationalRecord
 * @property {number | false} id
 *
 * @typedef ResizeBadge
 * @property {Point & { right?: number }} position
 * @property {number} diff
 * @property {string} scale
 *
 * @typedef {import("./gantt_model").Row & {
 *  grid: GridPosition,
 *  pills: Pill[],
 *  cellColors?: Record<string, string>,
 *  thumbnailUrl?: string
 * }} Row
 *
 * @typedef SubColumn
 * @property {number} columnIndex
 * @property {boolean} [isToday]
 * @property {DateTime} start
 * @property {DateTime} stop
 */

/** @type {[Omit<InteractionMode, "drag"> | DragActionMode, string][]} */
const INTERACTION_CLASSNAMES = [
    ["connect", "o_connect"],
    ["copy", "o_copying"],
    ["locked", "o_grabbing_locked"],
    ["reschedule", "o_grabbing"],
    ["resize", "o_resizing"],
];
const NEW_CONNECTOR_ID = "__connector__new";

const rtl = () => localization.direction === "rtl";

const clearObject = (obj) => {
    for (const key in obj) {
        delete obj[key];
    }
};

/**
 * Gantt Renderer
 *
 * @extends {Component<GanttRendererProps, any>}
 */
export class GanttRenderer extends Component {
    static components = {
        GanttConnector,
        GanttRendererControls,
        GanttTimeDisplayBadge,
        GanttRowProgressBar,
        Popover: GanttPopover,
        MultiSelectionButtons: GanttMultiSelectionButtons,
    };
    static props = [
        "model",
        "arch",
        "class",
        "create",
        "openDialog",
        "scrollPosition?",
        "multiCreateValues?",
        "contentRef?",
        "context?",
    ];

    static template = "web_gantt.GanttRenderer";
    static connectorCreatorTemplate = "web_gantt.GanttRenderer.ConnectorCreator";
    static headerTemplate = "web_gantt.GanttRenderer.Header";
    static pillTemplate = "web_gantt.GanttRenderer.Pill";
    static groupPillTemplate = "web_gantt.GanttRenderer.GroupPill";
    static rowContentTemplate = "web_gantt.GanttRenderer.RowContent";
    static rowHeaderTemplate = "web_gantt.GanttRenderer.RowHeader";
    static totalRowTemplate = "web_gantt.GanttRenderer.TotalRow";

    static getRowHeaderWidth = (width) => 100 / (width > 768 ? 6 : 3);

    setup() {
        this.model = this.props.model;

        this.gridRef = useRef("grid");
        this.cellContainerRef = useRef("cellContainer");

        this.actionService = useService("action");
        this.dialogService = useService("dialog");
        this.notificationService = useService("notification");
        this.orm = useService("orm");
        this.viewService = useService("view");

        this.keepLast = new KeepLast();

        this.defaultkanbanViewParams = null;

        this.is24HourFormat = is24HourFormat();

        /** @type {HoveredInfo} */
        this.hovered = {
            connector: null,
            hoverable: null,
            pill: null,
            collapsableColumnHeader: null,
        };

        /** @type {Interaction} */
        this.interaction = reactive(
            {
                mode: null,
                dragAction: "reschedule",
            },
            () => this.onInteractionChange()
        );
        this.onInteractionChange(); // Used to hook into "interaction"
        /** @type {Record<ConnectorId, ConnectorProps>} */
        this.connectors = reactive({});
        this.progressBarsReactive = reactive({ hoveredRowId: null });
        /** @type {ResizeBadge} */
        this.timeDisplayBadgeReactiveStart = reactive({});
        this.timeDisplayBadgeReactiveStop = reactive({});

        /** @type {Object[]} */
        this.columnsGroups = [];
        /** @type {Column[]} */
        this.columns = [];
        /** @type {Pill[]} */
        this.extraPills = [];
        /** @type {Record<PillId, Pill>} */
        this.pills = {}; // mapping to retrieve pills from pill ids
        /** @type {Row[]} */
        this.rows = [];
        /** @type {SubColumn[]} */
        this.subColumns = [];
        /** @type {Record<RowId, Pill[]>} */
        this.rowPills = {};

        this.mappingColToColumn = new Map();
        this.mappingColToSubColumn = new Map();
        this.cursorPosition = {
            x: 0,
            y: 0,
        };
        this.popover = usePopover(this.constructor.components.Popover, {
            onClose: () => {
                if (!this.preventClick) {
                    this.preventClick = true;
                    setTimeout(() => (this.preventClick = false), 250);
                }
                this.onCloseCurrentPopover?.();
            },
        });

        this.throttledComputeHoverParams = throttleForAnimation((ev) =>
            this.computeHoverParams(ev)
        );

        this.offHoursState = useState({});

        useExternalListener(window, "keydown", (ev) => this.onWindowKeyDown(ev));
        useExternalListener(window, "keyup", (ev) => this.onWindowKeyUp(ev));

        useExternalListener(
            window,
            "resize",
            debounce(() => {
                this.shouldComputeSomeWidths = true;
                this.render();
            }, 100)
        );

        useMultiHover({
            ref: this.gridRef,
            selector: ".o_gantt_group",
            exception: "o_gantt_cell_folded",
            related: ["data-row-id"],
            className: "o_gantt_group_hovered",
        });

        const scale = () => this.model.metaData.scale;

        // Draggable pills
        this.cellForDrag = { el: null, part: 0 };
        const dragState = useGanttDraggable({
            enable: () => Boolean(this.cellForDrag.el),
            // Refs and selectors
            ref: this.gridRef,
            hoveredCell: this.cellForDrag,
            elements: ".o_draggable",
            ignore: ".o_resize_handle,.o_connector_creator_bullet",
            cells: ".o_gantt_cell:not(.o_gantt_readonly)",
            // Style classes
            cellDragClassName: "o_gantt_cell o_drag_hover",
            ghostClassName: "o_dragged_pill_ghost",
            rtl,
            scale,
            getBadgesInitialDates: () => ({
                start: this.badgeInitialStartDate,
                stop: this.badgeInitialStopDate,
            }),
            addStickyCoordinates: this.addStickyCoordinates.bind(this),
            onWillStartDrag: this.cleanMultiSelection.bind(this),
            // Handlers
            onDragStart: ({ pill }) => {
                this.initBadges(pill);
                this.popover.close();
                this.setStickyPill(pill);
                this.toggleRowsReadonly(false);
                this.interaction.mode = "drag";
            },
            onDrag: this.updateBadges.bind(this),
            onDragEnd: () => {
                this.clearBadges();
                this.toggleRowsReadonly(true);
                this.setStickyPill();
                this.removeStickyCoordinates();
                this.interaction.mode = null;
            },
            onDrop: (params) => this.dragPillDrop(params),
        });

        // Resizable pills
        const resizeState = useGanttResizable({
            // Refs and selectors
            ref: this.gridRef,
            hoveredCell: this.cellForDrag,
            elements: ".o_resizable",
            innerPills: ".o_gantt_pill",
            // Other params
            handles: "o_resize_handle",
            edgeScrolling: { speed: 40, threshold: 150, direction: "horizontal" },
            scale,
            getBadgesInitialDates: () => ({
                start: this.badgeInitialStartDate,
                stop: this.badgeInitialStopDate,
            }),
            showHandles: (pillEl) => {
                const pill = this.pills[pillEl.dataset.pillId];
                const hideHandles = this.connectorDragState.dragging;
                return {
                    start: !pill.disableStartResize && !hideHandles,
                    end: !pill.disableStopResize && !hideHandles,
                };
            },
            rtl,
            onWillStartDrag: this.cleanMultiSelection.bind(this),
            // Handlers
            onDragStart: ({ pill, addClass }) => {
                this.initBadges(pill);
                this.popover.close();
                this.setStickyPill(pill);
                addClass(pill, "o_resized");
                this.interaction.mode = "resize";
            },
            onDrag: this.updateBadges.bind(this),
            onDragEnd: ({ pill, removeClass }) => {
                this.clearBadges();
                this.setStickyPill();
                removeClass(pill, "o_resized");
                this.interaction.mode = null;
            },
            onDrop: (params) => this.resizePillDrop(params),
        });

        // Draggable connector
        let initialPillId;
        this.connectorDragState = useGanttConnectorDraggable({
            ref: this.gridRef,
            elements: ".o_connector_creator_bullet",
            parentWrapper: ".o_gantt_cells .o_gantt_pill_wrapper",
            onWillStartDrag: this.cleanMultiSelection.bind(this),
            onDragStart: ({ sourcePill, x, y, addClass }) => {
                this.popover.close();
                initialPillId = sourcePill.dataset.pillId;
                addClass(sourcePill, "o_connector_creator_lock");
                this.setConnector({
                    id: NEW_CONNECTOR_ID,
                    highlighted: true,
                    sourcePoint: { left: x, top: y },
                    targetPoint: { left: x, top: y },
                });
                this.setStickyPill(sourcePill);
                this.interaction.mode = "connect";
            },
            onDrag: ({ connectorCenter, x, y }) => {
                this.setConnector({
                    id: NEW_CONNECTOR_ID,
                    sourcePoint: { left: connectorCenter.x, top: connectorCenter.y },
                    targetPoint: { left: x, top: y },
                });
            },
            onDragEnd: () => {
                this.setConnector({ id: NEW_CONNECTOR_ID, sourcePoint: null, targetPoint: null });
                this.setStickyPill();
                this.interaction.mode = null;
            },
            onDrop: ({ target }) => {
                if (initialPillId === target.dataset.pillId) {
                    return;
                }
                const { id: masterId } = this.pills[initialPillId].record;
                const { id: slaveId } = this.pills[target.dataset.pillId].record;
                this.model.createDependency(masterId, slaveId);
            },
        });

        this.dragStates = [dragState, resizeState];

        if (!this.model.hasMultiCreate) {
            // Un-draggable pills
            const unDragState = useGanttUndraggable({
                // Refs and selectors
                ref: this.gridRef,
                elements: ".o_undraggable",
                ignore: ".o_resize_handle,.o_connector_creator_bullet",
                edgeScrolling: { enabled: false },
                onWillStartDrag: this.cleanMultiSelection.bind(this),
                // Handlers
                onDragStart: () => {
                    this.interaction.mode = "locked";
                },
                onDragEnd: () => {
                    this.interaction.mode = null;
                },
            });
            this.dragStates.push(unDragState);
        }

        this.prepareSelectionFeature();

        onWillStart(this.computeDerivedParams);
        onWillUpdateProps(this.computeDerivedParams);

        this.virtualGrid = useVirtualGrid({
            scrollableRef: this.props.contentRef,
            initialScroll: this.props.scrollPosition,
            bufferCoef: 0.1,
            onChange: (changed) => {
                if ("columnsIndexes" in changed) {
                    this.shouldComputeGridColumns = true;
                }
                if ("rowsIndexes" in changed) {
                    this.shouldComputeGridRows = true;
                }
                this.render();
            },
        });

        onWillRender(this.onWillRender);
        onWillUnmount(this.onWillUnmount);

        useEffect(
            (content) => {
                content.addEventListener("scroll", this.throttledComputeHoverParams);
                return () => {
                    content.removeEventListener("scroll", this.throttledComputeHoverParams);
                };
            },
            () => [this.gridRef.el?.parentElement]
        );

        useEffect(() => {
            if (this.useFocusDate) {
                this.useFocusDate = false;
                this.focusDate(this.model.metaData.focusDate);
            }
        });

        useCallbackRecorder(
            this.env.getCurrentFocusDateCallBackRecorder,
            this.getCurrentFocusDate.bind(this)
        );
    }

    //-------------------------------------------------------------------------
    // Getters
    //-------------------------------------------------------------------------

    get foldedGridColumnCount() {
        return this.offHoursState.foldedGridColumnSpans?.length ?? this.columnCount;
    }

    get controlsProps() {
        return {
            displayExpandCollapseButtons: this.rows[0]?.isGroup, // all rows on same level have same type
            model: this.model,
            focusToday: () => this.focusToday(),
            getCurrentFocusDate: () => this.getCurrentFocusDate(),
        };
    }

    /**
     * @returns {boolean}
     */
    get hasRowHeaders() {
        const { groupedBy } = this.model.metaData;
        const { displayMode } = this.model.displayParams;
        return groupedBy.length || displayMode === "sparse";
    }

    get isDragging() {
        return this.dragStates.some((s) => s.dragging);
    }

    /**
     * @returns {boolean}
     */
    get isTouchDevice() {
        return isMobileOS() || hasTouch();
    }

    get allColumnsFolded() {
        if (
            this.model.metaData.displayUnavailability &&
            JSON.stringify(this.offHoursState.foldedColumns) ===
                JSON.stringify(this.foldableColumns)
        ) {
            return true;
        }
        return false;
    }

    //-------------------------------------------------------------------------
    // Methods
    //-------------------------------------------------------------------------

    addStickyCoordinates(rows, columns) {
        this.stickyGridRows = Object.assign({}, ...rows.map((row) => ({ [row]: true })));
        this.stickyGridColumns = Object.assign(
            {},
            ...columns.map((column) => ({ [column]: true }))
        );
        this.setSomeGridStyleProperties();
    }

    removeStickyCoordinates() {
        this.stickyGridRows = {};
        this.stickyGridColumns = {};
        this.setSomeGridStyleProperties();
    }

    appendCellGhost({ startCol, endCol, startRow, endRow }) {
        this.cellGhost.style = this.getGridPosition({
            row: [startRow, endRow],
            column: [startCol, endCol],
        });
        this.addStickyCoordinates([startRow, endRow], [startCol, endCol]);
        this.cellContainerRef.el.append(this.cellGhost);
    }

    drawCellGhosts(selectedCells) {
        this.removeCellGhosts();
        const rows = [];
        const columns = [];
        for (const selectedCell of selectedCells) {
            const clone = this.cellGhost.cloneNode();
            const { startRow, endRow, startCol, endCol } = this.getBlock(selectedCell);
            const row = [startRow, endRow];
            const column = [startCol, endCol];
            clone.style = this.getGridPosition({ row, column });
            this.cellContainerRef.el.append(clone);
            rows.push(...row);
            columns.push(...column);
        }
        this.addStickyCoordinates(rows, columns);
    }

    removeCellGhosts() {
        for (const ghost of this.gridRef.el.querySelectorAll(".o_cell_ghost")) {
            ghost.remove();
        }
        this.removeStickyCoordinates();
    }

    removeCellGhost() {
        this.cellGhost.remove();
        this.removeStickyCoordinates();
    }

    getAllCells(cells, action) {
        switch (action) {
            case "add":
                return this.selectedCells.union(cells);
            case "toggle":
                return this.selectedCells.symmetricDifference(cells);
            case "replace":
                return cells;
        }
    }

    updateMultiSelection({ startCol, endCol, startRow, endRow }, action) {
        const cells = this.getCellsInBlock({ startCol, endCol, startRow, endRow });
        this.selectedCells = this.getAllCells(cells, action);
        this.multiSelectionButtonsReactive.visible = Boolean(this.selectedCells.size);
        this.multiSelectionButtonsReactive.nbSelected = this.getSelectedRecordIds(
            this.selectedCells
        ).length;
        if (this.selectedCells.size === 1 && this.model.metaData.canPlan) {
            const selectedCell = [...this.selectedCells][0];
            const { startRow, startCol } = this.getBlock(selectedCell);
            const rowId = this.rowIdsByFirstRow[startRow];
            this.multiSelectionButtonsReactive.onPlan = () =>
                this.onPlan(rowId, startCol, startCol);
        } else {
            delete this.multiSelectionButtonsReactive.onPlan;
        }
    }

    createFromSelection() {
        if (!this.selectedCells?.size) {
            return false;
        }
        const cellBlocks = [];
        for (const selectedCell of this.selectedCells) {
            cellBlocks.push(this.getBlock(selectedCell));
        }
        cellBlocks.sort((b1, b2) => b1.startRow - b2.startRow || b1.startCol - b2.startCol);
        const firstBlock = cellBlocks[0];
        for (let i = 1; i < cellBlocks.length; i++) {
            const { startRow, startCol, endCol } = cellBlocks[i];
            if (startRow !== firstBlock.startRow || startCol !== firstBlock.endCol) {
                break;
            }
            firstBlock.endCol = endCol;
        }
        const rowId = this.rowIdsByFirstRow[firstBlock.startRow];
        this.onCreate(rowId, firstBlock.startCol, firstBlock.endCol - 1);
        return true;
    }

    cleanMultiSelection() {
        this.selectedCells = new Set();
        this.multiSelectionButtonsReactive.visible = false;
        this.multiSelectionButtonsReactive.nbSelected = 0;
        delete this.multiSelectionButtonsReactive.onPlan;
        this.removeCellGhosts();
    }

    prepareMultiSelectionButtonsReactive() {
        return reactive({
            onCancel: this.cleanMultiSelection.bind(this),
            onAdd: (multiCreateData) => {
                this.onMultiCreate(multiCreateData, this.selectedCells);
                this.cleanMultiSelection();
            },
            onDelete: () => {
                this.onMultiDelete(this.selectedCells);
                this.cleanMultiSelection();
            },
            nbSelected: 0,
            resModel: this.model.metaData.resModel,
            multiCreateView: this.model.metaData.multiCreateView || "",
            multiCreateValues: this.props.multiCreateValues,
            showMultiCreateTimeRange: this.model.showMultiCreateTimeRange,
            visible: false,
            context: this.model.searchParams.context,
        });
    }

    prepareSelectionFeature() {
        const scale = () => this.model.metaData.scale;
        const getDatetime = (col) => this.getSubColumnFromColNumber(col).start;

        this.selectedCells = new Set();
        this.cellGhost = document.createElement("div");
        this.cellGhost.classList.add("o_gantt_cell", "o_drag_hover", "o_cell_ghost", "pe-none");
        this.multiSelectionButtonsReactive = this.prepareMultiSelectionButtonsReactive();

        let action = null;
        const update = ({ startCol, endCol, startRow, endRow }) => {
            if (this.model.hasMultiCreate) {
                const cells = this.getCellsInBlock({ startCol, endCol, startRow, endRow });
                const selectedCells = this.getAllCells(cells, action);
                this.drawCellGhosts(selectedCells);
                return;
            }
            this.appendCellGhost({ startCol, endCol, startRow, endRow });
            const startDate = getDatetime(startCol);
            const stopDate = getDatetime(endCol);
            this.updateBadges(
                getBadges(this.cellGhost, [startDate], [stopDate], {
                    rtl: rtl(),
                    scale: scale(),
                })
            );
        };

        // Cells selection
        const selectState = useGanttSelectable({
            enable: () =>
                Boolean(this.cellForDrag.el) &&
                !this.cellForDrag.el.classList.contains("o_gantt_group") &&
                (this.model.metaData.canCellCreate || this.model.hasMultiCreate),
            ref: this.gridRef,
            hoveredCell: this.cellForDrag,
            elements: ".o_gantt_cell",
            edgeScrolling: {
                speed: 40,
                threshold: 150,
                direction: this.model.hasMultiCreate ? undefined : "horizontal",
            },
            hasMultiCreate: () => this.model.hasMultiCreate,
            rtl,
            scale,
            onDragStart: ({ startCol, endCol, startRow, endRow }) => {
                action = this.ctrlPressed ? "add" : "replace";
                update({ startCol, endCol, startRow, endRow });
            },
            onDrag: update,
            onDrop: ({ rowId, startCol, endCol, startRow, endRow }) => {
                if (this.model.hasMultiCreate) {
                    this.updateMultiSelection({ startCol, endCol, startRow, endRow }, action);
                } else {
                    this.removeCellGhost();
                    this.clearBadges();
                    this.onCreate(rowId, startCol, endCol - 1);
                }
                action = null;
            },
        });

        if (this.model.hasMultiCreate) {
            const pillSelectState = useGanttSelectable({
                enable: () =>
                    Boolean(this.cellForDrag.el) &&
                    !this.cellForDrag.el.classList.contains("o_gantt_group"),
                ref: this.gridRef,
                hoveredCell: this.cellForDrag,
                elements: ".o_undraggable",
                edgeScrolling: {
                    speed: 40,
                    threshold: 150,
                    direction: undefined,
                },
                hasMultiCreate: () => true,
                rtl,
                scale,
                onDragStart: ({ startCol, endCol, startRow, endRow }) => {
                    action = this.ctrlPressed ? "add" : "replace";
                    update({ startCol, endCol, startRow, endRow });
                },
                onDrag: update,
                onDrop: ({ startCol, endCol, startRow, endRow }) => {
                    this.updateMultiSelection({ startCol, endCol, startRow, endRow }, action);
                    action = null;
                },
            });
            this.dragStates.push(pillSelectState);
        }

        useBus(this.model.bus, "update", this.cleanMultiSelection.bind(this));

        useCallbackRecorder(
            this.env.createFromSelectionCallBackRecorder,
            this.createFromSelection.bind(this)
        );

        this.dragStates.push(selectState);
    }

    /**
     *
     * @param {Object} param
     * @param {Object} param.grid
     */
    addCoordinatesToCoarseGrid({ grid }) {
        if (grid.row) {
            this.coarseGridRows[this.getFirstGridRow({ grid })] = true;
            this.coarseGridRows[this.getLastGridRow({ grid })] = true;
        }
        if (grid.column) {
            this.coarseGridCols[this.getFirstGridCol({ grid })] = true;
            this.coarseGridCols[this.getLastGridCol({ grid })] = true;
        }
    }

    /**
     * @param {Pill} pill
     * @param {Group} group
     */
    addTo(pill, group) {
        group.pills.push(pill);
        group.aggregateValue++; // pill count
        return true;
    }

    /**
     * Conditional function for aggregating pills when grouping the gantt view
     * The first, unused parameter is added in case it's needed when overwriting the method.
     * @param {Row} row
     * @param {Group} group
     * @returns {boolean}
     */
    shouldAggregate(row, group) {
        return Boolean(group.pills.length);
    }

    /**
     * Aggregates overlapping pills in group rows.
     *
     * @param {Pill[]} pills
     * @param {Row} row
     */
    aggregatePills(pills, row) {
        /** @type {Record<number, Group>} */
        const groups = {};
        function getGroup(col) {
            if (!(col in groups)) {
                groups[col] = {
                    break: false,
                    col,
                    pills: [],
                    aggregateValue: 0,
                    grid: { column: [col, col + 1] },
                };
                // group.break = true means that the group cannot be merged with the previous one
                // We will merge groups that can be merged together (if this.shouldMergeGroups returns true)
            }
            return groups[col];
        }

        const lastCol = this.columnCount * this.model.metaData.scale.cellPart + 1;
        for (const pill of pills) {
            let addedInPreviousCol = false;
            let col;
            for (col = this.getFirstGridCol(pill); col < this.getLastGridCol(pill); col++) {
                const group = getGroup(col);
                const added = this.addTo(pill, group);
                if (addedInPreviousCol !== added) {
                    group.break = true;
                }
                addedInPreviousCol = added;
            }
            // here col = this.getLastGridCol(pill)
            if (addedInPreviousCol && col < lastCol) {
                const group = getGroup(col);
                group.break = true;
            }
        }

        const filteredGroups = Object.values(groups).filter((g) => this.shouldAggregate(row, g));

        if (this.shouldMergeGroups()) {
            return this.mergeGroups(filteredGroups);
        }

        return filteredGroups;
    }

    /**
     * Compute minimal levels required to display all pills without overlapping.
     * Side effect: level key is modified in pills.
     *
     * @param {Pill[]} pills
     */
    calculatePillsLevel(pills) {
        const firstPill = pills[0];
        firstPill.level = 0;
        const levels = [
            {
                pills: [firstPill],
                maxCol: this.getLastGridCol(firstPill) - 1,
            },
        ];
        for (const currentPill of pills.slice(1)) {
            const lastCol = this.getLastGridCol(currentPill) - 1;
            for (let l = 0; l < levels.length; l++) {
                const level = levels[l];
                if (this.getFirstGridCol(currentPill) > level.maxCol) {
                    currentPill.level = l;
                    level.pills.push(currentPill);
                    level.maxCol = lastCol;
                    break;
                }
            }
            if (isNaN(currentPill.level)) {
                currentPill.level = levels.length;
                levels.push({
                    pills: [currentPill],
                    maxCol: lastCol,
                });
            }
        }
        return levels.length;
    }

    makeSubColumn(start, delta, cellTime, time) {
        const subCellStart = dateAddFixedOffset(start, { [time]: delta * cellTime });
        const subCellStop = dateAddFixedOffset(start, {
            [time]: (delta + 1) * cellTime,
            seconds: -1,
        });
        return { start: subCellStart, stop: subCellStop };
    }

    computeVisibleColumns() {
        const [firstIndex, lastIndex] = this.virtualGrid.columnsIndexes;
        this.columnsGroups = [];
        this.columns = [];
        this.subColumns = [];
        this.coarseGridCols = {
            1: true,
            [this.columnCount * this.model.metaData.scale.cellPart + 1]: true,
        };

        const { displayUnavailability, globalStart, globalStop, scale } = this.model.metaData;
        const { cellPart, interval, unit } = scale;

        const now = DateTime.local();

        const nowStart = now.startOf(interval);
        const nowEnd = now.endOf(interval);

        const groupsLeftBound = DateTime.max(
            globalStart,
            localStartOf(
                globalStart.plus({
                    [interval]: this.getIndexInTotalGrid(firstIndex),
                }),
                unit
            )
        );
        const groupsRightBound = DateTime.min(
            localEndOf(
                globalStart.plus({
                    [interval]: this.getIndexInTotalGrid(lastIndex),
                }),
                unit
            ),
            globalStop
        );
        let currentGroup = null;
        for (let j = firstIndex; j <= lastIndex; j++) {
            const columnIndex = this.getIndexInTotalGrid(j);
            const col = columnIndex * cellPart + 1;
            const { start, stop } = this.getColumnFromColNumber(col);
            const span = this.offHoursState.foldedGridColumnSpans?.[j] || 1;
            const column = {
                index: columnIndex,
                grid: { column: [col, col + cellPart] },
                start,
                stop,
            };
            const isToday = nowStart <= start && start <= nowEnd;
            if (isToday) {
                column.isToday = true;
            }
            if (this.offHoursState.foldedColumns?.[columnIndex]) {
                column.stop = this.getColumnFromColNumber(col + (span - 1) * cellPart).stop;
                column.isFolded = true;
                column.grid.column[1] = col + span * cellPart;
            }
            if (displayUnavailability) {
                const foldableColumnsGroup = this.foldableColumnsMapping[columnIndex];
                column.isFoldable = foldableColumnsGroup
                    ? foldableColumnsGroup.stopIndex === columnIndex + span - 1
                        ? "stop"
                        : 1
                    : 0;
            }
            if (column.isFolded) {
                this.coarseGridCols[col] = true;
            } else {
                for (let i = 0; i < cellPart; i++) {
                    const subColumn = this.getSubColumnFromColNumber(col + i);
                    this.subColumns.push({ ...subColumn, isToday, columnIndex });
                    this.coarseGridCols[col + i] = true;
                }
            }
            this.columns.push(column);

            const groupStart = localStartOf(start, unit);
            if (!currentGroup || !groupStart.equals(currentGroup.start)) {
                const startingBound = DateTime.max(groupsLeftBound, groupStart);
                const endingBound = DateTime.min(groupsRightBound, localEndOf(groupStart, unit));
                const [groupFirstCol, groupLastCol] = this.getGridColumnFromDates(
                    startingBound,
                    endingBound
                );
                currentGroup = {
                    grid: { column: [groupFirstCol, groupLastCol] },
                    start: groupStart,
                    isFolded: columnIndex === 0 && groupLastCol < column.grid.column[1],
                };
                this.columnsGroups.push(currentGroup);
                this.coarseGridCols[groupFirstCol] = true;
                this.coarseGridCols[groupLastCol] = true;
            }
            if (j === lastIndex && currentGroup.grid.column[1] < column.grid.column[1]) {
                this.columnsGroups.push({
                    grid: { column: [currentGroup.grid.column[1], column.grid.column[1]] },
                    isFolded: true,
                });
            }
        }
    }

    computeVisibleRows() {
        this.coarseGridRows = {
            1: true,
            [this.getLastGridRow(this.rows[this.rows.length - 1])]: true,
        };
        const [rowStart, rowEnd] = this.virtualGrid.rowsIndexes;
        this.rowsToRender = new Set();
        for (const row of this.rows) {
            const [first, last] = row.grid.row;
            if (last <= rowStart + 1 || first > rowEnd + 1) {
                continue;
            }
            this.addToRowsToRender(row);
        }
    }

    getIndexInTotalGrid(index) {
        return this.offHoursState.mappingFoldedGridToTotalGridColumnIndex?.get(index) || index;
    }

    getColNumberInFoldedGrid(num) {
        return this.offHoursState.mappingTotalGridToFoldedGridSubColumns?.get(num) || num;
    }

    getFirstGridCol({ grid }) {
        const [first] = grid.column;
        return first;
    }

    getLastGridCol({ grid }) {
        const [, last] = grid.column;
        return last;
    }

    getFirstGridRow({ grid }) {
        const [first] = grid.row;
        return first;
    }

    getLastGridRow({ grid }) {
        const [, last] = grid.row;
        return last;
    }

    addToPillsToRender(pill) {
        this.pillsToRender.add(pill);
        this.addCoordinatesToCoarseGrid(pill);
    }

    addToRowsToRender(row) {
        this.rowsToRender.add(row);
        const [first, last] = row.grid.row;
        for (let i = first; i <= last; i++) {
            this.coarseGridRows[i] = true;
        }
    }

    /**
     * give bounds only
     */
    getVisibleCols() {
        const [firstIndex, lastIndex] = this.virtualGrid.columnsIndexes;
        const startIndex = this.getIndexInTotalGrid(firstIndex);
        const endIndex = this.getIndexInTotalGrid(lastIndex);
        const { cellPart } = this.model.metaData.scale;
        const firstVisibleCol = 1 + cellPart * startIndex;
        const lastVisibleCol = 1 + cellPart * (endIndex + 1);
        return [firstVisibleCol, lastVisibleCol];
    }

    /**
     * give bounds only
     */
    getVisibleRows() {
        const [firstIndex, lastIndex] = this.virtualGrid.rowsIndexes;
        const firstVisibleRow = firstIndex + 1;
        const lastVisibleRow = lastIndex + 1;
        return [firstVisibleRow, lastVisibleRow];
    }

    computeVisiblePills() {
        this.pillsToRender = new Set();

        const [firstVisibleCol, lastVisibleCol] = this.getVisibleCols();
        const [firstVisibleRow, lastVisibleRow] = this.getVisibleRows();

        const isOut = (pill, filterOnRow = true) =>
            this.getFirstGridCol(pill) > lastVisibleCol ||
            this.getLastGridCol(pill) < firstVisibleCol ||
            (filterOnRow &&
                (this.getFirstGridRow(pill) > lastVisibleRow ||
                    this.getLastGridRow(pill) - 1 < firstVisibleRow));

        const getRowPills = (row, filterOnRow) =>
            (this.rowPills[row.id] || []).filter((pill) => !isOut(pill, filterOnRow));

        for (const row of this.rowsToRender) {
            for (const rowPill of getRowPills(row)) {
                this.addToPillsToRender(rowPill);
            }
            if (!row.isGroup && row.unavailabilities?.length) {
                row.cellColors = this.getRowCellColors(row);
            }
        }

        if (this.stickyPillId) {
            this.addToPillsToRender(this.pills[this.stickyPillId]);
        }

        if (this.totalRow) {
            this.totalRow.pills = getRowPills(this.totalRow, false);
            for (const pill of this.totalRow.pills) {
                this.addCoordinatesToCoarseGrid({ grid: omit(pill.grid, "row") });
            }
        }
    }

    computeVisibleConnectors() {
        const visibleConnectorIds = new Set([NEW_CONNECTOR_ID]);

        for (const pill of this.pillsToRender) {
            const row = this.getRowFromPill(pill);
            if (row.isGroup) {
                continue;
            }
            for (const connectorId of this.mappingPillToConnectors[pill.id] || []) {
                visibleConnectorIds.add(connectorId);
            }
        }

        this.connectorsToRender = [];
        for (const connectorId in this.connectors) {
            if (!visibleConnectorIds.has(connectorId)) {
                continue;
            }
            this.connectorsToRender.push(this.connectors[connectorId]);
            const { sourcePillId, targetPillId } = this.mappingConnectorToPills[connectorId];
            if (sourcePillId) {
                this.addToPillsToRender(this.pills[sourcePillId]);
            }
            if (targetPillId) {
                this.addToPillsToRender(this.pills[targetPillId]);
            }
        }
    }

    getRowFromPill(pill) {
        return this.rowByIds[pill.rowId];
    }

    getColInCoarseGridKeys() {
        return Object.keys({ ...this.coarseGridCols, ...this.stickyGridColumns });
    }

    getRowInCoarseGridKeys() {
        return Object.keys({ ...this.coarseGridRows, ...this.stickyGridRows });
    }

    computeColsTemplate() {
        const colsTemplate = [];
        const colInCoarseGridKeys = this.getColInCoarseGridKeys();
        for (let i = 0; i < colInCoarseGridKeys.length - 1; i++) {
            const x = +colInCoarseGridKeys[i];
            const y = +colInCoarseGridKeys[i + 1];
            const { distance, flexible } = this.getSubColumnsDistance(x, y, this.cellPartWidth);
            const colName = `c${x}`;
            colsTemplate.push(`[${colName}]minmax(${distance}px,${+flexible}fr)`);
        }
        colsTemplate.push(`[c${colInCoarseGridKeys.at(-1)}]`);
        return colsTemplate.join("");
    }

    getSubColumnsDistance(start, stop, cellPartWidth) {
        const { cellPart } = this.model.metaData.scale;
        if (this.offHoursState.foldedGridColumnSpans) {
            const X = this.getColNumberInFoldedGrid(start);
            const Y = this.getColNumberInFoldedGrid(stop);
            let distance = 0;
            let flexible = true;
            for (let j = X; j < Y; j++) {
                if (
                    this.offHoursState.foldedColumns[
                        this.getIndexInTotalGrid(Math.floor((j - 1) / cellPart))
                    ]
                ) {
                    distance += 36 / cellPart;
                    if (this.offHoursState.foldedGridColumnSpans.length > 1) {
                        flexible = false;
                    }
                } else {
                    distance += cellPartWidth;
                }
            }
            return { distance, flexible };
        }
        return { distance: (stop - start) * cellPartWidth, flexible: true };
    }

    computeRowsTemplate() {
        const rowsTemplate = [];
        const rowInCoarseGridKeys = this.getRowInCoarseGridKeys();
        for (let i = 0; i < rowInCoarseGridKeys.length - 1; i++) {
            const x = +rowInCoarseGridKeys[i];
            const y = +rowInCoarseGridKeys[i + 1];
            const rowName = `r${x}`;
            const height = this.gridRows.slice(x - 1, y - 1).reduce((a, b) => a + b, 0);
            rowsTemplate.push(`[${rowName}]${height}px`);
        }
        rowsTemplate.push(`[r${rowInCoarseGridKeys.at(-1)}]`);
        return rowsTemplate.join("");
    }

    computeSomeWidths() {
        const { cellPart, minimalColumnWidth } = this.model.metaData.scale;
        this.contentRefWidth = this.props.contentRef.el?.clientWidth ?? document.body.clientWidth;
        const rowHeaderWidthPercentage = this.hasRowHeaders
            ? this.constructor.getRowHeaderWidth(this.contentRefWidth)
            : 0;
        this.rowHeaderWidth = this.hasRowHeaders
            ? Math.round((rowHeaderWidthPercentage * this.contentRefWidth) / 100)
            : 0;
        if (this.foldedGridColumnCount === 1) {
            this.cellPartWidth = Math.floor(
                (this.contentRefWidth - this.rowHeaderWidth) / cellPart
            );
            this.columnWidth = this.cellPartWidth * cellPart;
            this.virtualGrid.setColumnsWidths([this.columnWidth]);
            this.totalWidth = null;
            return;
        }
        this.visibleCellContainerWidth = this.contentRefWidth - this.rowHeaderWidth;
        const hiddenColumnsCount =
            this.offHoursState.foldedColumns?.reduce(
                (sum, folded) => (folded ? sum + 1 : sum),
                0
            ) || 0;
        const foldedColumnsCount =
            this.foldedGridColumnCount + hiddenColumnsCount - this.columnCount;
        const columnWidth = Math.floor(
            (this.visibleCellContainerWidth - 36 * foldedColumnsCount) /
                (this.foldedGridColumnCount - foldedColumnsCount)
        );
        const rectifiedColumnWidth = Math.max(columnWidth, minimalColumnWidth);
        this.cellPartWidth = Math.floor(rectifiedColumnWidth / cellPart);
        this.columnWidth = this.cellPartWidth * cellPart;
        let offPeriod = 0;
        const columnWidths = this.offHoursState.foldedColumns
            ? this.offHoursState.foldedColumns?.reduce((res, val, index) => {
                  if (val === 1) {
                      offPeriod++;
                  } else {
                      if (offPeriod > 0) {
                          res.push(36);
                      }
                      res.push(this.columnWidth);
                      offPeriod = 0;
                  }
                  if (index === this.offHoursState.foldedColumns.length - 1 && offPeriod > 0) {
                      res.push(36);
                  }
                  return res;
              }, [])
            : new Array(this.foldedGridColumnCount).fill(this.columnWidth);
        this.virtualGrid.setColumnsWidths(columnWidths);
        if (columnWidth <= minimalColumnWidth) {
            // overflow
            this.totalWidth = columnWidths.reduce((sum, w) => sum + w, 0) + this.rowHeaderWidth;
        } else {
            this.totalWidth = null;
        }
    }

    computeDerivedParams() {
        const { rows: modelRows } = this.model.data;

        if (this.shouldRenderConnectors()) {
            /** @type {Record<number, { masterIds: number[], pills: Record<RowId, Pill> }>} */
            this.mappingRecordToPillsByRow = {};
            /** @type {Record<RowId, Record<number, Pill>>} */
            this.mappingRowToPillsByRecord = {};
            /** @type {Record<ConnectorId, { sourcePillId: PillId, targetPillId: PillId }>} */
            this.mappingConnectorToPills = {};
            /** @type {Record<PillId, ConnectorId>} */
            this.mappingPillToConnectors = {};
        }

        this.mappingCellToRecords = {};
        this.rowIdsByFirstRow = {};

        const { displayUnavailability, globalStart, globalStop, scale, startDate, stopDate } =
            this.model.metaData;
        this.columnCount = diffColumn(globalStart, globalStop, scale.interval);
        if (
            !this.currentStartDate ||
            diffColumn(this.currentStartDate, startDate, "day") ||
            diffColumn(this.currentStopDate, stopDate, "day") ||
            this.currentScaleId !== scale.id
        ) {
            this.useFocusDate = true;
            this.mappingColToColumn = new Map();
            this.mappingColToSubColumn = new Map();
            delete this.offHoursState.foldedColumns;
        }
        this.currentStartDate = startDate;
        this.currentStopDate = stopDate;
        this.currentScaleId = scale.id;

        this.currentGridRow = 1;
        this.gridRows = [];
        this.nextPillId = 1;

        this.pills = {}; // mapping to retrieve pills from pill ids
        this.rows = [];
        this.rowPills = {};
        this.rowByIds = {};

        const prePills = this.getPills();

        let pillsToProcess = [...prePills];
        for (const row of modelRows) {
            const result = this.processRow(row, pillsToProcess);
            this.rows.push(...result.rows);
            pillsToProcess = result.pillsToProcess;
        }

        const { displayTotalRow } = this.model.metaData;
        if (displayTotalRow) {
            this.totalRow = this.getTotalRow(prePills);
        }

        if (this.shouldRenderConnectors()) {
            this.initializeConnectors();
            this.generateConnectors();
        }

        if (displayUnavailability) {
            this.computeUnavailabilityPeriods();
            this.computeFoldedGrid();
        }
        this.shouldComputeSomeWidths = true;
        this.shouldComputeGridColumns = true;
        this.shouldComputeGridRows = true;
    }

    computeDerivedParamsFromHover() {
        const { scale } = this.model.metaData;

        const { connector, collapsableColumnHeader, hoverable } = this.hovered;

        // Update cell in drag
        const isCellHovered = hoverable?.matches(".o_gantt_cell");
        this.cellForDrag.el = isCellHovered ? hoverable : null;
        this.cellForDrag.part = 0;
        if (isCellHovered && scale.cellPart > 1) {
            this.cellForDrag.part = getHoveredCellPart(
                hoverable,
                this.cursorPosition.x,
                scale.cellPart,
                rtl()
            );
        }

        if (this.isDragging) {
            this.progressBarsReactive.hoveredRowId = null;
            return;
        }

        if (!this.connectorDragState.dragging) {
            // Highlight connector
            const hoveredConnectorId = connector?.dataset.connectorId;
            for (const connectorId in this.connectors) {
                if (connectorId !== hoveredConnectorId) {
                    this.toggleConnectorHighlighting(connectorId, false);
                }
            }
            if (hoveredConnectorId) {
                this.progressBarsReactive.hoveredRowId = null;
                return this.toggleConnectorHighlighting(hoveredConnectorId, true);
            }
        }

        this.toggleCollapsableColumnHeaderHighlighting(collapsableColumnHeader);
        // Update progress bars
        this.progressBarsReactive.hoveredRowId =
            hoverable && !hoverable.classList.contains("o_gantt_cell_folded")
                ? hoverable.dataset.rowId
                : null;
    }

    /**
     * @param {ConnectorId} connectorId
     */
    deleteConnector(connectorId) {
        delete this.connectors[connectorId];
        delete this.mappingConnectorToPills[connectorId];
    }

    get isAutoPlan() {
        return ["consumeBuffer", "maintainBuffer"].includes(this.model.metaData.rescheduleMethod);
    }

    /**
     * @param {Object} params
     * @param {Element} params.pill
     * @param {Element} params.cellSrc
     * @param {Element} params.cellDst
     * @param {number} params.diff
     */
    async dragPillDrop({ pill, cellSrc, cellDst, diff }) {
        const { rowId } = cellDst.dataset;
        const { dateStartField, dateStopField, scale } = this.model.metaData;
        const { cellTime, time } = scale;
        const { record } = this.pills[pill.dataset.pillId];
        const params = this.getScheduleParams(pill);
        const isCopyMode = this.interaction.dragAction === "copy";

        params.start =
            (diff || isCopyMode) &&
            dateAddFixedOffset(record[dateStartField], { [time]: cellTime * diff });
        params.stop =
            (diff || isCopyMode) &&
            dateAddFixedOffset(record[dateStopField], { [time]: cellTime * diff });
        params.rowId = rowId;

        const schedule = this.model.getSchedule(params);

        let copyResId;
        let fallbackSchedule;
        if (isCopyMode) {
            copyResId = await this.model.copy(
                record.id,
                schedule,
                this.openPlanDialogCallback.bind(this)
            );
        } else {
            const fallbackParams = {
                ...this.getUndoAfterDragRecordData(record),
                rowId: cellSrc.dataset.rowId,
            };
            fallbackSchedule = this.model.getSchedule(fallbackParams);
            if (this.isAutoPlan) {
                await this.model.rescheduleAccordingToDependency(
                    record.id,
                    schedule,
                    this.rescheduleAccordingToDependencyCallback.bind(this)
                );
            } else {
                await this.model.reschedule(
                    record.id,
                    schedule,
                    this.openPlanDialogCallback.bind(this)
                );
            }
        }

        // If the pill lands on a closed group -> open it
        if (cellDst.classList.contains("o_gantt_group") && this.model.isClosed(rowId)) {
            this.model.toggleRow(rowId);
        }

        this.displayUndoNotificationAfterDrag(
            copyResId || record.id,
            this.interaction.dragAction,
            fallbackSchedule
        );
    }

    /**
     * @param {number} resId
     * @param {string} dragAction
     * @param {Object} [fallbackData]
     */
    displayUndoNotificationAfterDrag(resId, dragAction, fallbackData = {}) {
        if (!(dragAction === "copy" || dragAction === "reschedule")) {
            return;
        }
        if (dragAction === "reschedule" && this.isAutoPlan) {
            return;
        }
        const messages = this.getUndoAfterDragMessages(dragAction);
        this.closeNotificationFn?.();
        this.closeNotificationFn = this.notificationService.add(
            markup`<i class="fa fa-fw fa-check"></i><span class="ms-1">${messages.success}</span>`,
            {
                type: "success",
                buttons: [
                    {
                        name: "Undo",
                        icon: "fa-undo",
                        onClick: async () => {
                            // Undo the last drag & drop action
                            const result = await this.model.orm.call(
                                this.model.metaData.resModel,
                                "gantt_undo_drag_drop",
                                [resId, dragAction, fallbackData]
                            );
                            this.closeNotificationFn?.();
                            if (result) {
                                this.closeNotificationFn = this.notificationService.add(
                                    markup`<i class="fa fa-fw fa-check"></i><span class="ms-1">${messages.undo}</span>`,
                                    { type: "success" }
                                );
                            } else {
                                this.closeNotificationFn = this.notificationService.add(
                                    markup`<i class="fa fa-fw fa-check"></i><span class="ms-1">${messages.failure}</span>`,
                                    { type: "danger" }
                                );
                            }
                            this.model.fetchData();
                        },
                    },
                ],
            }
        );
    }

    /**
     * @param {string} dragAction
     * @returns {Object}
     */
    getUndoAfterDragMessages(dragAction) {
        if (dragAction === "copy") {
            return {
                success: _t("Record duplicated"),
                undo: _t("Record removed"),
                failure: _t("Record could not be removed"),
            };
        }
        return {
            success: _t("Record rescheduled"),
            undo: _t("Record reschedule undone"),
            failure: _t("Failed to undo reschedule"),
        };
    }

    /**
     * @param {Object} record
     * @returns {Object}
     */
    getUndoAfterDragRecordData(record) {
        const { dateStartField, dateStopField } = this.model.metaData;
        return {
            start: record[dateStartField],
            stop: record[dateStopField],
        };
    }

    /**
     * @param {Partial<Pill>} pill
     * @returns {Pill}
     */
    enrichPill(pill) {
        const { colorField, fields, pillDecorations, progressField } = this.model.metaData;

        pill.displayName = this.getDisplayName(pill);

        const classes = [];

        if (pillDecorations) {
            const pillContext = Object.assign({}, user.context);
            for (const [fieldName, value] of Object.entries(pill.record)) {
                const field = fields[fieldName];
                switch (field.type) {
                    case "date": {
                        pillContext[fieldName] = value ? serializeDate(value) : false;
                        break;
                    }
                    case "datetime": {
                        pillContext[fieldName] = value ? serializeDateTime(value) : false;
                        break;
                    }
                    default: {
                        pillContext[fieldName] = value;
                    }
                }
            }

            for (const decoration in pillDecorations) {
                const expr = pillDecorations[decoration];
                if (evaluateBooleanExpr(expr, pillContext)) {
                    classes.push(decoration);
                }
            }
        }

        if (colorField) {
            pill._color = getColorIndex(pill.record[colorField]);
            classes.push(`o_gantt_color_${pill._color}`);
        }

        if (progressField) {
            pill._progress = pill.record[progressField] || 0;
        }

        pill.className = classes.join(" ");

        return pill;
    }

    focusDate(date, focusGroup = true) {
        const { globalStart, globalStop, scale } = this.model.metaData;
        const { cellPart, interval, unit } = scale;
        const focusedDate = focusGroup ? localStartOf(date, unit) : date;
        const diff = focusedDate.diff(globalStart);
        const totalDiff = globalStop.diff(globalStart);
        const factor = diff / totalDiff;
        if (!focusGroup && (factor < 0 || 1 < factor)) {
            return false;
        }
        const rtlFactor = rtl() ? -1 : 1;
        if (this.columnCount === this.foldedGridColumnCount) {
            const scrollLeft = factor * this.cellContainerRef.el.clientWidth;
            this.props.contentRef.el.scrollLeft = rtlFactor * scrollLeft;
            return true;
        }
        const { column, delta } = this.getSubColumnFromDate(focusedDate);
        const col = 1 + diffColumn(globalStart, column, interval) * cellPart + delta;
        const { distance } = this.getSubColumnsDistance(1, col, this.cellPartWidth);
        this.props.contentRef.el.scrollLeft = rtlFactor * distance;
        return true;
    }

    focusFirstPill(rowId) {
        const pill = this.rowPills[rowId][0];
        if (pill) {
            const col = this.getFirstGridCol(pill);
            const { start: date } = this.getColumnFromColNumber(col);
            this.focusDate(date);
        }
    }

    focusToday() {
        return this.focusDate(DateTime.local().startOf("day"), false);
    }

    generateConnectors() {
        this.nextConnectorId = 1;
        this.setConnector({
            id: NEW_CONNECTOR_ID,
            highlighted: true,
            sourcePoint: null,
            targetPoint: null,
        });
        for (const slaveId in this.mappingRecordToPillsByRow) {
            const { masterIds, pills: slavePills } = this.mappingRecordToPillsByRow[slaveId];
            for (const masterId of masterIds) {
                if (!(masterId in this.mappingRecordToPillsByRow)) {
                    continue;
                }
                const { pills: masterPills } = this.mappingRecordToPillsByRow[masterId];
                for (const [slaveRowId, targetPill] of Object.entries(slavePills)) {
                    for (const [masterRowId, sourcePill] of Object.entries(masterPills)) {
                        if (
                            masterRowId === slaveRowId ||
                            !(
                                slaveId in this.mappingRowToPillsByRecord[masterRowId] ||
                                masterId in this.mappingRowToPillsByRecord[slaveRowId]
                            ) ||
                            Object.keys(this.mappingRecordToPillsByRow[slaveId].pills).every(
                                (rowId) =>
                                    rowId !== masterRowId &&
                                    masterId in this.mappingRowToPillsByRecord[rowId]
                            ) ||
                            Object.keys(this.mappingRecordToPillsByRow[masterId].pills).every(
                                (rowId) =>
                                    rowId !== slaveRowId &&
                                    slaveId in this.mappingRowToPillsByRecord[rowId]
                            )
                        ) {
                            this.setConnector(...this.getConnecterValues(sourcePill, targetPill));
                        }
                    }
                }
            }
        }
    }

    /**
     * @param {Pill} sourcePill
     * @param {Pill} targetPill
     */
    getConnecterValues(sourcePill, targetPill) {
        return [
            { alert: this.getConnectorAlert(sourcePill.record, targetPill.record) },
            sourcePill.id,
            targetPill.id,
            this.shouldConnectorBeDashed(sourcePill),
        ];
    }

    shouldConnectorBeDashed(sourcePill) {
        return false;
    }

    /**
     * @param {Group} group
     * @param {Group} previousGroup
     */
    getAggregateValue(group, previousGroup) {
        // both groups have the same pills by construction
        // here the aggregateValue is the pill count
        return group.aggregateValue;
    }

    /**
     * @param {number} startCol
     * @param {number} stopCol
     * @param {boolean} [roundUpStop=true]
     */
    getColumnStartStop(startCol, stopCol) {
        const { start } = this.getColumnFromColNumber(startCol);
        const { stop } = this.getColumnFromColNumber(stopCol);
        return { start, stop };
    }

    /**
     *
     * @param {number} masterRecord
     * @param {number} slaveRecord
     * @returns {import("./gantt_connector").ConnectorAlert | null}
     */
    getConnectorAlert(masterRecord, slaveRecord) {
        const { dateStartField, dateStopField } = this.model.metaData;
        if (slaveRecord[dateStartField] < masterRecord[dateStopField]) {
            if (slaveRecord[dateStartField] < masterRecord[dateStartField]) {
                return "error";
            } else {
                return "warning";
            }
        }
        return null;
    }

    /**
     * @param {Row} row
     * @param {Column} column
     * @return {Object}
     */
    ganttCellAttClass(row, column) {
        return {
            o_sample_data_disabled: this.isDisabled(row),
            o_gantt_today: column.isToday,
            o_gantt_cell_folded: column.isFolded,
            o_gantt_group: row.isGroup,
            o_gantt_hoverable: this.isHoverable(row),
            o_group_open: !this.model.isClosed(row.id),
            o_gantt_readonly: row.readonly,
        };
    }

    getCurrentFocusDate() {
        const { globalStart, globalStop } = this.model.metaData;
        const rtlFactor = rtl() ? -1 : 1;
        const cellGridMiddleX =
            rtlFactor * this.props.contentRef.el.scrollLeft +
            (this.contentRefWidth + this.rowHeaderWidth) / 2;
        let factor = (cellGridMiddleX - this.rowHeaderWidth) / this.cellContainerRef.el.clientWidth;
        if (this.columnCount !== this.foldedGridColumnCount) {
            let columnWidthSum = 0;
            for (let i = 0; i < this.foldedGridColumnCount; i++) {
                if (this.offHoursState.foldedColumns[this.getIndexInTotalGrid(i)]) {
                    columnWidthSum += 36;
                } else {
                    columnWidthSum += this.columnWidth;
                }
                if (columnWidthSum > cellGridMiddleX - this.rowHeaderWidth) {
                    factor = (this.getIndexInTotalGrid(i) + 1) / this.columnCount;
                    break;
                }
            }
        }
        const totalDiff = globalStop.diff(globalStart);
        const diff = factor * totalDiff;
        const focusDate = globalStart.plus(diff);
        return focusDate;
    }

    /**
     * @param {"top"|"bottom"} vertical the vertical alignment of the connector creator
     * @returns {{ vertical: "top"|"bottom", horizontal: "left"|"right" }}
     */
    getConnectorCreatorAlignment(vertical) {
        const alignment = { vertical };
        if (rtl()) {
            alignment.horizontal = vertical === "top" ? "right" : "left";
        } else {
            alignment.horizontal = vertical === "top" ? "left" : "right";
        }
        return alignment;
    }

    /**
     * Get schedule parameters
     *
     * @param {Element} pill
     * @returns {Object} - An object containing parameters needed for scheduling the pill.
     */
    getScheduleParams(pill) {
        return {};
    }

    /**
     * This function will add a 'label' property to each
     * non-consolidated pill included in the pills list.
     * This new property is a string meant to replace
     * the text displayed on a pill.
     *
     * @param {Pill} pill
     */
    getDisplayName(pill) {
        const { computePillDisplayName, dateStartField, dateStopField, scale } =
            this.model.metaData;
        const { id: scaleId } = scale;
        const { record } = pill;

        if (!computePillDisplayName) {
            return record.display_name;
        }

        const startDate = record[dateStartField];
        const stopDate = record[dateStopField];
        const yearlessDateFormat = omit(DateTime.DATE_SHORT, "year");

        const daysDelta = Interval.fromDateTimes(
            startDate.startOf("day"),
            stopDate.startOf("day")
        ).toDuration(["day", "hour"]).days;
        const spanAccrossDays =
            daysDelta &&
            (daysDelta > 2 ||
                (startDate.endOf("day").diff(startDate, "hours").toObject().hours >= 3 &&
                    stopDate.diff(stopDate.startOf("day"), "hours").toObject().hours >= 3));

        /** @type {string[]} */
        const labels = [];

        // Start & End Dates
        if (scaleId === "year" && !spanAccrossDays) {
            labels.push(startDate.toLocaleString(yearlessDateFormat));
        } else if (
            scaleId === "year" ||
            (spanAccrossDays &&
                (startDate < this.currentStartDate || this.currentStopDate.endOf("day") < stopDate))
        ) {
            labels.push(startDate.toLocaleString(yearlessDateFormat));
            labels.push(stopDate.toLocaleString(yearlessDateFormat));
        }

        // Start & End Times
        if (record.allocated_hours && !spanAccrossDays && ["week", "month"].includes(scaleId)) {
            const durationStr = this.getDurationStr(record);
            labels.push(
                toLocaleDateTimeString(startDate, { showDate: false }),
                `${toLocaleDateTimeString(stopDate, { showDate: false })}${durationStr}`
            );
        }

        /** @type {string[]} */
        const labelElements = [labels.join(" - ")];

        // Original Display Name
        if (scaleId !== "month" || !record.allocated_hours || spanAccrossDays) {
            labelElements.push(record.display_name);
        }

        return labelElements.filter((el) => !!el).join(" ");
    }

    /**
     * @param {RelationalRecord} record
     */
    getDurationStr(record) {
        const durationStr = formatFloatTime(record.allocated_hours, {
            noLeadingZeroHour: true,
        }).replace(/(:00|:)/g, "h");
        return ` (${durationStr})`;
    }

    /**
     * @param {Pill} pill
     */
    getGroupPillDisplayName(pill) {
        return pill.aggregateValue;
    }

    /**
     * @param {{ column?: [number, number], row?: [number, number] }} position
     */
    getGridPosition(position) {
        const style = [];
        const keys = Object.keys(pick(position, "column", "row"));
        for (const key of keys) {
            const prefix = key.slice(0, 1);
            const [first, last] = position[key];
            style.push(`grid-${key}:${prefix}${first}/${prefix}${last}`);
        }
        return style.join(";");
    }

    /**
     * @param {{ column?: [number, number], row?: [number, number] }} position
     */
    getGroupHeaderStyle(position) {
        return this.getGridPosition(position) + `;max-width: ${this.visibleCellContainerWidth}px`;
    }

    setSomeGridStyleProperties() {
        const rowsTemplate = this.computeRowsTemplate();
        const colsTemplate = this.computeColsTemplate();
        this.gridRef.el.style.setProperty("--Gantt__GridRows-grid-template-rows", rowsTemplate);
        this.gridRef.el.style.setProperty(
            "--Gantt__GridColumns-grid-template-columns",
            colsTemplate
        );
    }

    getGridStyle() {
        const rowsTemplate = this.computeRowsTemplate();
        const colsTemplate = this.computeColsTemplate();
        const style = {
            "--Gantt__RowHeader-width": `${this.rowHeaderWidth}px`,
            "--Gantt__Pill-height": "25px",
            "--Gantt__Thumbnail-max-height": "16px",
            "--Gantt__GridRows-grid-template-rows": rowsTemplate,
            "--Gantt__GridColumns-grid-template-columns": colsTemplate,
        };
        if (this.totalWidth !== null) {
            style.width = `${this.totalWidth}px`;
        }
        return Object.entries(style)
            .map((entry) => entry.join(":"))
            .join(";");
    }

    /**
     * @param {RelationalRecord} record
     * @returns {Partial<Pill>}
     */
    getPill(record) {
        const { canEdit, dateStartField, dateStopField, disableDrag, globalStart, globalStop } =
            this.model.metaData;

        const startOutside = record[dateStartField] < globalStart;

        let recordDateStopField = record[dateStopField];
        if (this.model.dateStopFieldIsDate()) {
            recordDateStopField = recordDateStopField.plus({ day: 1 });
        }

        const stopOutside = recordDateStopField > globalStop;

        /** @type {DateTime} */
        const pillStartDate = startOutside ? globalStart : record[dateStartField];
        /** @type {DateTime} */
        const pillStopDate = stopOutside ? globalStop : recordDateStopField;

        const disableStartResize = !canEdit || startOutside;
        const disableStopResize = !canEdit || stopOutside;

        /** @type {Partial<Pill>} */
        const pill = {
            disableDrag: disableDrag || disableStartResize || disableStopResize,
            disableStartResize,
            disableStopResize,
            grid: { column: this.getGridColumnFromDates(pillStartDate, pillStopDate) },
            record,
        };

        return pill;
    }

    getGridColumnFromDates(startDate, stopDate) {
        const { globalStart, scale } = this.model.metaData;
        const { cellPart, interval } = scale;
        const { column: column1, delta: delta1 } = this.getSubColumnFromDate(startDate);
        const { column: column2, delta: delta2 } = this.getSubColumnFromDate(stopDate, false);
        const firstCol = 1 + diffColumn(globalStart, column1, interval) * cellPart + delta1;
        const span = diffColumn(column1, column2, interval) * cellPart + delta2 - delta1;
        return [firstCol, firstCol + span];
    }

    getSubColumnFromDate(date, onLeft = true) {
        const { interval, cellPart, cellTime, time } = this.model.metaData.scale;
        const column = date.startOf(interval);
        let delta;
        if (onLeft) {
            delta = 0;
            for (let i = 1; i < cellPart; i++) {
                const subCellStart = dateAddFixedOffset(column, { [time]: i * cellTime });
                if (subCellStart <= date) {
                    delta += 1;
                } else {
                    break;
                }
            }
        } else {
            delta = cellPart;
            for (let i = cellPart - 1; i >= 0; i--) {
                const subCellStart = dateAddFixedOffset(column, { [time]: i * cellTime });
                if (subCellStart >= date) {
                    delta -= 1;
                } else {
                    break;
                }
            }
        }
        return { column, delta };
    }

    getSubColumnFromColNumber(col) {
        let subColumn = this.mappingColToSubColumn.get(col);
        if (!subColumn) {
            const { globalStart, scale } = this.model.metaData;
            const { interval, cellPart, cellTime, time } = scale;
            const delta = (col - 1) % cellPart;
            const columnIndex = (col - 1 - delta) / cellPart;
            const start = globalStart.plus({ [interval]: columnIndex });
            subColumn = this.makeSubColumn(start, delta, cellTime, time);
            this.mappingColToSubColumn.set(col, subColumn);
        }
        return subColumn;
    }

    getColumnIndexFromColNumber(col) {
        const { cellPart } = this.model.metaData.scale;
        const delta = (col - 1) % cellPart;
        return (col - 1 - delta) / cellPart;
    }

    getColumnFromColNumber(col) {
        let column = this.mappingColToColumn.get(col);
        if (!column) {
            const { globalStart, scale } = this.model.metaData;
            const { interval } = scale;
            const columnIndex = this.getColumnIndexFromColNumber(col);
            const start = globalStart.plus({ [interval]: columnIndex });
            const stop = start.endOf(interval);
            column = { start, stop };
            this.mappingColToColumn.set(col, column);
        }
        return column;
    }

    /**
     * @param {PillId} pillId
     */
    getPillEl(pillId) {
        return this.getPillWrapperEl(pillId).querySelector(".o_gantt_pill");
    }

    /**
     * @param {Object} group
     * @param {number} maxAggregateValue
     * @param {boolean} consolidate
     */
    getPillFromGroup(group, maxAggregateValue, consolidate) {
        const { excludeField, field, maxValue } = this.model.metaData.consolidationParams;

        const minColor = 215;
        const maxColor = 100;

        const newPill = {
            id: `__pill__${this.nextPillId++}`,
            level: 0,
            aggregateValue: group.aggregateValue,
            grid: group.grid,
        };

        // Enrich the aggregates with consolidation data
        if (consolidate && field) {
            newPill.consolidationValue = 0;
            for (const pill of group.pills) {
                if (!pill.record[excludeField]) {
                    newPill.consolidationValue += pill.record[field];
                }
            }
            newPill.consolidationMaxValue = maxValue;
            newPill.consolidationExceeded =
                newPill.consolidationValue > newPill.consolidationMaxValue;
        }

        if (consolidate && maxValue) {
            const status = newPill.consolidationExceeded ? "danger" : "success";
            newPill.className = `bg-${status} border-${status}`;
            newPill.displayName = newPill.consolidationValue;
        } else {
            const color =
                minColor -
                Math.round((newPill.aggregateValue - 1) / maxAggregateValue) *
                    (minColor - maxColor);
            newPill.style = `background-color:rgba(${color},${color},${color},0.6)`;
            newPill.displayName = this.getGroupPillDisplayName(newPill);
        }

        return newPill;
    }

    /**
     * There are two forms of pills: pills comming from fetched records
     * and pills that are some kind of aggregation of the previous.
     *
     * Here we create the pills of the firs type.
     *
     * The basic properties (independent of rows,...) of the pills of
     * the first type should be computed here.
     *
     * @returns {Partial<Pill>[]}
     */
    getPills() {
        const { records } = this.model.data;
        const { dateStartField } = this.model.metaData;
        const pills = [];
        for (const record of records) {
            const pill = this.getPill(record);
            pills.push(this.enrichPill(pill));
        }
        return pills.sort(
            (p1, p2) =>
                p1.grid.column[0] - p2.grid.column[0] ||
                p1.record[dateStartField] - p2.record[dateStartField]
        );
    }

    /**
     * @param {PillId} pillId
     */
    getPillWrapperEl(pillId) {
        const pillSelector = `:scope > [data-pill-id="${pillId}"]`;
        return this.cellContainerRef.el?.querySelector(pillSelector);
    }

    /**
     * Get domain of records for plan dialog in the gantt view.
     *
     * @param {Object} state
     * @returns {any[][]}
     */
    getPlanDialogDomain() {
        const { dateStartField, dateStopField } = this.model.metaData;
        const newDomain = Domain.removeDomainLeaves(this.env.searchModel.globalDomain, [
            dateStartField,
            dateStopField,
        ]);
        return Domain.and([
            newDomain,
            ["|", [dateStartField, "=", false], [dateStopField, "=", false]],
        ]).toList({});
    }

    /**
     * @param {PillId} pillId
     * @param {boolean} onRight
     */
    getPoint(pillId, onRight) {
        if (rtl()) {
            onRight = !onRight;
        }
        const pillEl = this.getPillEl(pillId);
        const pillRect = pillEl.getBoundingClientRect();
        return {
            left: pillRect.left + (onRight ? pillRect.width : 0),
            top: pillRect.top + pillRect.height / 2,
        };
    }

    async _getKanbanViewParams() {
        const { dateStartField, dateStopField, kanbanViewId, fields, resModel } =
            this.model.metaData;

        if (kanbanViewId !== undefined) {
            const result = await this.viewService.loadViews({
                resModel,
                views: [[kanbanViewId, "kanban"]],
            });

            const arch = result.views.kanban.arch;
            const archXmlDoc = parseXML(arch.replace(/&amp;nbsp;/g, nbsp));
            // remove some elements/attributes from archXmlDoc
            archXmlDoc.removeAttribute("highlight_color");
            const menu = archXmlDoc.querySelector(
                `templates [t-name=${KanbanRecord.KANBAN_MENU_ATTRIBUTE}]`
            );
            menu?.remove();

            const { relatedModels } = result;
            const { ArchParser } = viewRegistry.get("kanban");
            const archInfo = new ArchParser().parse(archXmlDoc, relatedModels, resModel);
            return {
                archInfo,
                ...extractFieldsFromArchInfo(archInfo, fields),
            };
        }
        if (!this.defaultkanbanViewParams) {
            // These values to be assigned outside of arch to properly generate POT files.
            const nameString = _t("Name");
            const startString = _t("Start");
            const stopString = _t("Stop");
            const arch = `
                <kanban>
                    <templates>
                        <field name="${dateStartField}"/>
                        <field name="${dateStopField}"/>
                        <t t-name="${KanbanRecord.KANBAN_CARD_ATTRIBUTE}">
                            <ul class="p-0 mb-0 list-unstyled">
                                <li class="pe-2">
                                    <strong>${nameString}</strong>: <field name="display_name"/>
                                </li>
                                <li class="pe-2">
                                    <strong>${startString}</strong>: <span t-esc="luxon.DateTime.fromISO(record.${dateStartField}.raw_value).toFormat('f')"/>
                                </li>
                                <li class="pe-2">
                                    <strong>${stopString}</strong>: <span t-esc="luxon.DateTime.fromISO(record.${dateStopField}.raw_value).toFormat('f')"/>
                                </li>
                            </ul>
                        </t>
                    </templates>
                </kanban>
            `;
            const archXmlDoc = parseXML(arch.replace(/&amp;nbsp;/g, nbsp));

            const relatedModels = { [resModel]: { fields } };
            const { ArchParser } = viewRegistry.get("kanban");
            const archInfo = new ArchParser().parse(archXmlDoc, relatedModels, resModel);
            this.defaultkanbanViewParams = {
                archInfo,
                ...extractFieldsFromArchInfo(archInfo, fields),
            };
        }
        return this.defaultkanbanViewParams;
    }

    /**
     * @param {Pill} pill
     */
    async getPopoverProps(pill) {
        const { record } = pill;
        const { id: resId, display_name: displayName } = record;
        const { canEdit, popoverArchParams, resModel } = this.model.metaData;
        const kanbanViewParams = popoverArchParams.bodyTemplate
            ? {}
            : await this._getKanbanViewParams();
        return {
            ...popoverArchParams,
            kanbanViewParams,
            KanbanRecord,
            title: displayName,
            context: { ...record },
            actionContext: this.props.context,
            resId,
            resModel,
            reloadOnClose: () => {
                this.onCloseCurrentPopover = () => {
                    delete this.onCloseCurrentPopover;
                    this.model.fetchData();
                };
            },
            buttons: [
                {
                    id: "open_view_edit_dialog",
                    text: canEdit ? _t("Edit") : _t("View"),
                    class: "btn btn-sm btn-primary",
                    // Sync with the mutex to wait for potential changes on the view
                    onClick: () =>
                        this.model.mutex.exec(
                            () => this.props.openDialog({ resId }) // (canEdit is also considered in openDialog)
                        ),
                },
            ],
        };
    }

    /**
     * @param {Row} row
     */
    getProgressBarProps(row) {
        return {
            progressBar: row.progressBar,
            reactive: this.progressBarsReactive,
            rowId: row.id,
        };
    }

    /**
     * @param {Row} row
     */
    getRowCellColors(row) {
        const { unavailabilities } = row;
        const { cellPart } = this.model.metaData.scale;
        // We assume that the unavailabilities have been normalized
        // (i.e. are naturally ordered and are pairwise disjoint).
        // A subCell is considered unavailable (and greyed) when totally covered by
        // an unavailability.
        let index = 0;
        let j = 0;
        /** @type {Record<string, string>} */
        const cellColors = {};
        const subSlotUnavailabilities = [];
        for (const subColumn of this.subColumns) {
            const { isToday, start, stop, columnIndex } = subColumn;
            if (index < unavailabilities.length) {
                let subSlotUnavailable = 0;
                for (let i = index; i < unavailabilities.length; i++) {
                    const u = unavailabilities[i];
                    if (stop > u.stop) {
                        index++;
                        continue;
                    } else if (u.start <= start) {
                        subSlotUnavailable = 1;
                    }
                    break;
                }
                subSlotUnavailabilities.push(subSlotUnavailable);
                if ((j + 1) % cellPart === 0) {
                    const style = getCellColor(cellPart, subSlotUnavailabilities, isToday);
                    subSlotUnavailabilities.splice(0, cellPart);
                    if (style) {
                        cellColors[columnIndex] = style;
                    }
                }
                j++;
            }
        }
        return cellColors;
    }

    getFromData(groupedByField, resId, key, defaultVal) {
        const values = this.model.data[key];
        if (groupedByField) {
            return values[groupedByField]?.[resId ?? false] || defaultVal;
        }
        return values.__default?.false || defaultVal;
    }

    /**
     * @param {string} [groupedByField]
     * @param {false|number} [resId]
     * @returns {Object}
     */
    getRowProgressBar(groupedByField, resId) {
        return this.getFromData(groupedByField, resId, "progressBars", null);
    }

    /**
     * @param {string} [groupedByField]
     * @param {false|number} [resId]
     * @returns {{ start: DateTime, stop: DateTime }[]}
     */
    getRowUnavailabilities(groupedByField, resId) {
        return this.getFromData(groupedByField, resId, "unavailabilities", []);
    }

    /**
     * @param {"t0" | "t1" | "t2"} type
     * @returns {number}
     */
    getRowTypeHeight(type) {
        return { t0: 24, t1: 25, t2: 10 }[type];
    }

    getRowTitleStyle(row) {
        return `grid-column: ${row.groupLevel + 2} / -1`;
    }

    openPlanDialogCallback() {}

    getSelectCreateDialogProps(params) {
        const domain = this.getPlanDialogDomain();
        const schedule = this.model.getDialogContext(params);
        return {
            title: _t("Plan"),
            resModel: this.model.metaData.resModel,
            context: schedule,
            domain,
            noCreate: !this.model.metaData.canCellCreate,
            onSelected: (resIds) => {
                if (resIds.length) {
                    this.model.reschedule(resIds, schedule, this.openPlanDialogCallback.bind(this));
                }
            },
        };
    }

    /**
     * @param {Pill[]} pills
     */
    getTotalRow(pills) {
        const preRow = {
            groupLevel: 0,
            id: "[]",
            rows: [],
            name: _t("Total"),
            recordIds: pills.map(({ record }) => record.id),
        };

        this.currentGridRow = 1;
        const result = this.processRow(preRow, pills);
        const [totalRow] = result.rows;
        const allPills = this.rowPills[totalRow.id] || [];
        const maxAggregateValue = Math.max(...allPills.map((p) => p.aggregateValue));

        totalRow.factor = maxAggregateValue ? 90 / maxAggregateValue : 0;

        return totalRow;
    }

    highlightPill(pillId, highlighted) {
        const pill = this.pills[pillId];
        if (!pill) {
            return;
        }
        const pillWrapper = this.getPillWrapperEl(pillId);
        if (pillWrapper) {
            pillWrapper.classList.toggle("highlight", highlighted);
            pillWrapper.classList.toggle(
                "o_connector_creator_highlight",
                highlighted && this.connectorDragState.dragging
            );
        }
    }

    initializeConnectors() {
        for (const connectorId in this.connectors) {
            this.deleteConnector(connectorId);
        }
    }

    isPillSmall(pill) {
        return this.cellPartWidth * pill.grid.column[1] < pill.displayName.length * 10;
    }

    /**
     * @param {Row} row
     */
    isDisabled(row = null) {
        return this.model.useSampleModel;
    }

    /**
     * @param {Row} row
     */
    isHoverable(row) {
        return !this.model.useSampleModel;
    }

    /**
     * @param {Group[]} groups
     * @returns {Group[]}
     */
    mergeGroups(groups) {
        if (groups.length <= 1) {
            return groups;
        }
        const index = Math.floor(groups.length / 2);
        const left = this.mergeGroups(groups.slice(0, index));
        const right = this.mergeGroups(groups.slice(index));
        const group = right[0];
        if (!group.break) {
            const previousGroup = left.pop();
            group.break = previousGroup.break;
            group.grid.column[0] = previousGroup.grid.column[0];
            group.aggregateValue = this.getAggregateValue(group, previousGroup);
        }
        return [...left, ...right];
    }

    onWillRender() {
        if (this.noDisplayedConnectors && this.shouldRenderConnectors()) {
            delete this.noDisplayedConnectors;
            this.computeDerivedParams();
        }

        if (this.shouldComputeSomeWidths) {
            this.computeSomeWidths();
        }

        if (this.shouldComputeSomeWidths || this.shouldComputeGridColumns) {
            this.computeVisibleColumns();
        }

        if (this.shouldComputeGridRows) {
            this.virtualGrid.setRowsHeights(this.gridRows);
            this.computeVisibleRows();
        }

        if (
            this.shouldComputeSomeWidths ||
            this.shouldComputeGridColumns ||
            this.shouldComputeGridRows
        ) {
            delete this.shouldComputeSomeWidths;
            delete this.shouldComputeGridColumns;
            delete this.shouldComputeGridRows;
            this.computeVisiblePills();
            if (this.shouldRenderConnectors()) {
                this.computeVisibleConnectors();
            } else {
                this.noDisplayedConnectors = true;
            }
        }

        if (this.containsReadonlyGroup()) {
            this.setupInitialReadonly();
        }

        delete this.shouldComputeSomeWidths;
        delete this.shouldComputeGridColumns;
        delete this.shouldComputeGridRows;
    }

    onWillUnmount() {
        this.closeNotificationFn?.();
    }

    pushGridRows(gridRows) {
        for (const key of ["t0", "t1", "t2"]) {
            if (key in gridRows) {
                const types = new Array(gridRows[key]).fill(this.getRowTypeHeight(key));
                this.gridRows.push(...types);
            }
        }
    }

    processPillsAsRows(row, pills) {
        const rows = [];
        const parsedId = JSON.parse(row.id);
        if (pills.length) {
            for (const pill of pills) {
                const { id: resId, display_name: name } = pill.record;
                const subRow = {
                    id: JSON.stringify([...parsedId, { id: resId }]),
                    resId,
                    name,
                    groupLevel: row.groupLevel + 1,
                    recordIds: [resId],
                    fromServer: row.fromServer,
                    parentResId: row.resId ?? row.parentResId,
                    parentGroupedField: row.groupedByField || row.parentGroupedField,
                };
                const res = this.processRow(subRow, [pill], false);
                rows.push(...res.rows);
            }
        } else {
            const subRow = {
                id: JSON.stringify([...parsedId, {}]),
                resId: false,
                name: "",
                groupLevel: row.groupLevel + 1,
                recordIds: [],
                fromServer: row.fromServer,
                parentResId: row.resId ?? row.parentResId,
                parentGroupedField: row.groupedByField || row.parentGroupedField,
            };
            const res = this.processRow(subRow, [], false);
            rows.push(...res.rows);
        }

        return rows;
    }

    /**
     * @param {Row} row
     * @param {Pill[]} pills
     * @param {boolean} [processAsGroup=false]
     */
    processRow(row, pills, processAsGroup = true) {
        const { dependencyField, displayUnavailability, fields } = this.model.metaData;
        const { displayMode } = this.model.displayParams;
        const {
            consolidate,
            fromServer,
            groupedByField,
            groupLevel,
            id,
            name,
            parentResId,
            parentGroupedField,
            resId,
            rows,
            recordIds,
            __extra__,
        } = row;

        // compute the subset pills at row level
        const remainingPills = [];
        let rowPills = [];
        const groupPills = [];
        const isMany2many = groupedByField && fields[groupedByField].type === "many2many";
        for (const pill of pills) {
            const { record } = pill;
            const pushPill = recordIds.includes(record.id);
            let keepPill = false;
            if (pushPill && isMany2many) {
                const value = record[groupedByField];
                if (Array.isArray(value) && value.length > 1) {
                    keepPill = true;
                }
            }
            if (pushPill) {
                const rowPill = { ...pill };
                rowPills.push(rowPill);
                groupPills.push(pill);
            }
            if (!pushPill || keepPill) {
                remainingPills.push(pill);
            }
        }

        if (displayMode === "sparse" && __extra__) {
            const rows = this.processPillsAsRows(row, groupPills);
            return { rows, pillsToProcess: remainingPills };
        }

        const isGroup = displayMode === "sparse" ? processAsGroup : Boolean(rows);

        const gridRowTypes = isGroup ? { t0: 1 } : { t1: 1, t2: +!this.isTouchDevice };
        if (rowPills.length) {
            if (isGroup) {
                if (this.shouldComputeAggregateValues(row)) {
                    const groups = this.aggregatePills(rowPills, row);
                    const maxAggregateValue = Math.max(
                        ...groups.map((group) => group.aggregateValue)
                    );
                    rowPills = groups.map((group) =>
                        this.getPillFromGroup(group, maxAggregateValue, consolidate)
                    );
                } else {
                    rowPills = [];
                }
            } else {
                const level = this.calculatePillsLevel(rowPills);
                gridRowTypes.t1 = level;
            }
        }

        const progressBar = this.getRowProgressBar(groupedByField, resId);
        if (progressBar && this.isTouchDevice && (!gridRowTypes.t1 || gridRowTypes.t1 === 1)) {
            // In mobile: rows span over 2 rows to alllow progressbars to properly display
            gridRowTypes.t1 = (gridRowTypes.t1 || 0) + 1;
        }
        if (row.id !== "[]") {
            this.pushGridRows(gridRowTypes);
        }

        const subRowsCount = Object.values(gridRowTypes).reduce((acc, val) => acc + val, 0);
        const gridRow = [this.currentGridRow, this.currentGridRow + subRowsCount];
        const subKey = `${gridRow[0]}_${gridRow[1]}`;
        if (this.model.hasMultiCreate && !isGroup) {
            this.rowIdsByFirstRow[this.currentGridRow] = row.id;
        }
        for (const rowPill of rowPills) {
            rowPill.id = `__pill__${this.nextPillId++}`;
            const pillFirstRow = this.currentGridRow + rowPill.level;
            rowPill.grid = {
                ...rowPill.grid, // rowPill is a shallow copy of a prePill (possibly copied several times)
                row: [pillFirstRow, pillFirstRow + 1],
            };
            if (!isGroup) {
                const { record } = rowPill;
                if (this.shouldRenderRecordConnectors(record)) {
                    if (!this.mappingRecordToPillsByRow[record.id]) {
                        this.mappingRecordToPillsByRow[record.id] = {
                            masterIds: record[dependencyField],
                            pills: {},
                        };
                    }
                    this.mappingRecordToPillsByRow[record.id].pills[id] = rowPill;
                    if (!this.mappingRowToPillsByRecord[id]) {
                        this.mappingRowToPillsByRecord[id] = {};
                    }
                    this.mappingRowToPillsByRecord[id][record.id] = rowPill;
                }
                if (this.model.hasMultiCreate) {
                    const [firstRow, lastRow] = rowPill.grid.column;
                    for (let col = firstRow; col < lastRow; col++) {
                        const key = `${subKey}_${col}_${col + 1}`;
                        if (!this.mappingCellToRecords[key]) {
                            this.mappingCellToRecords[key] = [];
                        }
                        this.mappingCellToRecords[key].push(rowPill.record);
                    }
                }
            }
            rowPill.rowId = id;
            this.pills[rowPill.id] = rowPill;
        }

        this.rowPills[id] = rowPills; // all row pills

        /** @type {Row} */
        const processedRow = {
            cellColors: {},
            fromServer,
            groupedByField,
            groupLevel,
            id,
            isGroup,
            name,
            progressBar,
            resId,
            grid: { row: gridRow },
        };
        if (displayUnavailability && !isGroup) {
            processedRow.unavailabilities = this.getRowUnavailabilities(
                parentGroupedField || groupedByField,
                parentResId ?? resId
            );
        }

        this.rowByIds[id] = processedRow;

        this.currentGridRow += subRowsCount;

        const field = this.model.metaData.thumbnails[groupedByField];
        if (field) {
            const model = this.model.metaData.fields[groupedByField].relation;
            processedRow.thumbnailUrl = url("/web/image", {
                model,
                id: resId,
                field,
            });
        }

        const result = { rows: [processedRow], pillsToProcess: remainingPills };

        if (!this.model.isClosed(id)) {
            if (rows) {
                let pillsToProcess = groupPills;
                for (const subRow of rows) {
                    const res = this.processRow(subRow, pillsToProcess);
                    result.rows.push(...res.rows);
                    pillsToProcess = res.pillsToProcess;
                }
            } else if (displayMode === "sparse" && processAsGroup) {
                const rows = this.processPillsAsRows(row, groupPills);
                result.rows.push(...rows);
            }
        }

        return result;
    }

    /**
     * @param {Object} params
     * @param {Element} params.pill
     * @param {number} params.diff
     * @param {"start" | "end"} params.direction
     */
    async resizePillDrop({ pill, diff, direction }) {
        const { dateStartField, dateStopField, scale } = this.model.metaData;
        const { cellTime, time } = scale;
        const { record } = this.pills[pill.dataset.pillId];
        const params = this.getScheduleParams(pill);

        if (direction === "start") {
            params.start = dateAddFixedOffset(record[dateStartField], { [time]: cellTime * diff });
            if (params.start > record[dateStopField]) {
                return this.notificationService.add(
                    _t("Starting date cannot be after the ending date"),
                    {
                        type: "warning",
                    }
                );
            }
        } else {
            params.stop = dateAddFixedOffset(record[dateStopField], { [time]: cellTime * diff });
            if (params.stop < record[dateStartField]) {
                return this.notificationService.add(
                    _t("Ending date cannot be before the starting date"),
                    {
                        type: "warning",
                    }
                );
            }
        }
        const schedule = this.model.getSchedule(params);
        const fallbackParams = this.getUndoAfterDragRecordData(record);
        const fallbackSchedule = this.model.getSchedule(fallbackParams);

        await this.model.reschedule(record.id, schedule, this.openPlanDialogCallback.bind(this));
        this.displayUndoNotificationAfterDrag(
            record.id,
            this.interaction.dragAction,
            fallbackSchedule
        );
    }

    /**
     * @param {Partial<ConnectorProps>} params
     * @param {PillId | null} [sourceId=null]
     * @param {PillId | null} [targetId=null]
     */
    setConnector(params, sourceId = null, targetId = null, dashed = null) {
        const connectorParams = { ...params };
        const connectorId = params.id || `__connector__${this.nextConnectorId++}`;

        if (sourceId) {
            connectorParams.sourcePoint = () => this.getPoint(sourceId, true);
        }

        if (targetId) {
            connectorParams.targetPoint = () => this.getPoint(targetId, false);
        }

        if (dashed) {
            connectorParams.dashed = true;
        }

        if (this.connectors[connectorId]) {
            Object.assign(this.connectors[connectorId], connectorParams);
        } else {
            this.connectors[connectorId] = {
                id: connectorId,
                highlighted: false,
                displayButtons: false,
                ...connectorParams,
            };
            this.mappingConnectorToPills[connectorId] = {
                sourcePillId: sourceId,
                targetPillId: targetId,
            };
        }

        if (sourceId) {
            if (!this.mappingPillToConnectors[sourceId]) {
                this.mappingPillToConnectors[sourceId] = [];
            }
            this.mappingPillToConnectors[sourceId].push(connectorId);
        }

        if (targetId) {
            if (!this.mappingPillToConnectors[targetId]) {
                this.mappingPillToConnectors[targetId] = [];
            }
            this.mappingPillToConnectors[targetId].push(connectorId);
        }
    }

    /**
     * @param {HTMLElement} [pillEl]
     */
    setStickyPill(pillEl) {
        this.stickyPillId = pillEl ? pillEl.dataset.pillId : null;
    }

    /**
     * @returns {boolean}: whether one of the "groupedBy" fields of the model is readonly
     */
    containsReadonlyGroup() {
        return this.model.metaData.groupedBy.some((groupedByField) => {
            return this.model.metaData.fields[groupedByField].readonly;
        });
    }

    /**
     * For all rows to render, specify whether the row is grouped by a readonly
     * field or is a child of a row grouped by a readonly field - by setting its'
     * 'readonly' and 'readonlyChild' properties.
     */
    setupInitialReadonly() {
        let foundReadonlyField = false;
        const readonlyGroups = [];
        const readonlyChildren = [];
        for (const groupedByField of this.props.model.metaData.groupedBy) {
            // Field itself is readonly
            if (this.model.metaData.fields[groupedByField].readonly) {
                foundReadonlyField = true;
                readonlyGroups.push(groupedByField);
            }
            // There is a readonly parent group
            else if (foundReadonlyField) {
                readonlyChildren.push(groupedByField);
            }
        }

        for (const row of this.rowsToRender) {
            row.readonlyChild = readonlyChildren.includes(row.groupedByField);
            row.readonly = readonlyGroups.includes(row.groupedByField) || row.readonlyChild;
        }
    }

    /**
     * @param {boolean} addReadonly: whether to add or remove the readonly class
     */
    toggleRowsReadonly(addReadonly) {
        if (!this.stickyPillId || !this.containsReadonlyGroup()) {
            return;
        }
        const startingRowId = this.pills[this.stickyPillId].rowId;
        const rowIdx = this.rows.findIndex((r) => r.id === startingRowId);
        this.toggleReadonly(this.rows[rowIdx], addReadonly);
        // Also update rows that are part of the same "child group"
        if (this.rows[rowIdx].readonlyChild) {
            for (const row of this.rows.slice(0, rowIdx).reverse()) {
                if (!row.readonlyChild) {
                    break;
                }
                this.toggleReadonly(row, addReadonly);
            }
            for (const row of this.rows.slice(rowIdx + 1, this.rows.length)) {
                if (!row.readonlyChild) {
                    break;
                }
                this.toggleReadonly(row, addReadonly);
            }
        }
    }

    toggleReadonly(row, addReadonly) {
        for (const cell of getCellsOnRow(this.gridRef.el, row.id)) {
            if (addReadonly) {
                cell.classList.add("o_gantt_readonly");
            } else {
                cell.classList.remove("o_gantt_readonly");
            }
        }
    }

    /**
     * @param {Row} row
     */
    shouldComputeAggregateValues(row) {
        return true;
    }

    shouldMergeGroups() {
        return true;
    }

    /**
     * Returns whether connectors should be rendered or not.
     * The connectors won't be rendered on sampleData as we can't be sure that data are coherent.
     * The connectors won't be rendered on mobile as the usability is not guarantied.
     *
     * @return {boolean}
     */
    shouldRenderConnectors() {
        return (
            this.model.metaData.dependencyField && !this.model.useSampleModel && !this.env.isSmall
        );
    }

    /**
     * Returns whether connectors should be rendered on particular records or not.
     * This method is intended to be overridden in particular modules in order to set particular record's condition.
     *
     * @param {RelationalRecord} record
     * @return {boolean}
     */
    shouldRenderRecordConnectors(record) {
        return this.shouldRenderConnectors();
    }

    /*
     * This function is made to be overwrite in other module to enable the highlight feature.
     */
    onConnectorHover() {
        return false;
    }

    /**
     * @param {ConnectorId | null} connectorId
     * @param {boolean} highlighted
     */
    toggleConnectorHighlighting(connectorId, highlighted) {
        const connector = this.connectors[connectorId];
        if (!connector || (!connector.highlighted && !highlighted)) {
            return;
        }

        connector.highlighted = highlighted;
        connector.displayButtons = highlighted;

        if (this.onConnectorHover()) {
            const { sourcePillId, targetPillId } = this.mappingConnectorToPills[connectorId];

            this.highlightPill(sourcePillId, highlighted);
            this.highlightPill(targetPillId, highlighted);
        }
    }

    computeUnavailabilityPeriods() {
        const { cellPart, unit } = this.model.metaData.scale;
        const columns = [...Array(this.columnCount).keys()].map((i) =>
            this.getColumnFromColNumber(i * cellPart + 1)
        );
        this.foldableColumns = Array(this.columnCount);
        let allNull = true;
        for (const row of this.rows) {
            if (row.isGroup) {
                continue;
            }
            const { unavailabilities } = row;
            // We assume that the unavailabilities have been normalized
            // (i.e. are naturally ordered and are pairwise disjoint).
            allNull = true;
            if (unavailabilities) {
                let index = 0;
                for (let columnIndex = 0; columnIndex < columns.length; columnIndex++) {
                    if (this.foldableColumns[columnIndex] === 0) {
                        continue;
                    }
                    this.foldableColumns[columnIndex] = 0;
                    if (index < unavailabilities.length) {
                        const { start, stop } = columns[columnIndex];
                        for (let i = index; i < unavailabilities.length; i++) {
                            const u = unavailabilities[i];
                            if (stop > u.stop) {
                                index++;
                                continue;
                            } else if (u.start <= start) {
                                this.foldableColumns[columnIndex] = 1;
                                allNull = false;
                            }
                            break;
                        }
                    }
                }
            }
            if (allNull) {
                break;
            }
        }
        if (allNull) {
            this.foldableColumns.fill(0);
        } else {
            for (const pill of Object.values(this.pills)) {
                this.foldableColumns.fill(
                    0,
                    Math.floor((pill.grid.column[0] - 1) / cellPart),
                    Math.ceil((pill.grid.column[1] - 1) / cellPart)
                );
            }
        }

        this.foldableColumnsMapping = {};
        let foldableGroupNum = 0;
        let foldableSubSet;
        for (let i = 0; i < this.foldableColumns.length; i++) {
            if (this.foldableColumns[i]) {
                const next = this.foldableColumns[i + 1];
                const previous = this.foldableColumns[i - 1];
                if (!previous) {
                    foldableSubSet = { foldableGroupNum };
                    foldableGroupNum++;
                    foldableSubSet.startIndex = i;
                }
                if (next === 1) {
                    this.foldableColumnsMapping[i] = foldableSubSet;
                    continue;
                }
                if (!previous && unit !== "week") {
                    this.foldableColumns[i] = 0;
                    continue;
                }
                foldableSubSet.stopIndex = i;
                this.foldableColumnsMapping[i] = foldableSubSet;
            }
        }
    }

    computeFoldedGrid() {
        this.shouldComputeSomeWidths = true;
        if (this.offHoursState.foldedColumns && !this.offHoursState.foldedColumns.includes(1)) {
            clearObject(this.offHoursState);
            return;
        }
        let foldedColumns = this.foldableColumns;
        if (this.offHoursState.foldedColumns?.length === this.columnCount) {
            foldedColumns = zipWith(
                this.foldableColumns,
                this.offHoursState.foldedColumns,
                (a, b) => a & b
            );
        }

        // aggregate unavailability columns
        let offPeriod = 0;
        this.offHoursState.foldedGridColumnSpans = foldedColumns.reduce((res, val, index) => {
            if (val === 1) {
                offPeriod++;
            } else {
                if (offPeriod > 0) {
                    res.push(offPeriod);
                }
                res.push(1);
                offPeriod = 0;
            }
            if (index === foldedColumns.length - 1 && offPeriod > 0) {
                res.push(offPeriod);
            }
            return res;
        }, []);
        const { cellPart, unit } = this.model.metaData.scale;
        this.offHoursState.mappingTotalGridToFoldedGridSubColumns = new Map();
        this.offHoursState.foldedColumns = [];
        const halfCut = Math.floor(cellPart / 2);
        let count = 0;
        for (let index = 0; index < this.offHoursState.foldedGridColumnSpans.length; index++) {
            const val = this.offHoursState.foldedGridColumnSpans[index];
            if (val > 1) {
                for (let j = 0; j < val; j++) {
                    for (let i = 1; i <= cellPart; i++) {
                        const targetIndex =
                            j === 0
                                ? index * cellPart + (i <= halfCut ? i : halfCut + 1)
                                : j === val - 1
                                ? index * cellPart + (i <= halfCut ? halfCut + 1 : i)
                                : index * cellPart + halfCut + 1;
                        this.offHoursState.mappingTotalGridToFoldedGridSubColumns.set(
                            count * cellPart + i,
                            targetIndex
                        );
                    }
                    count++;
                    this.offHoursState.foldedColumns.push(1);
                }
            } else {
                for (let i = 1; i <= cellPart; i++) {
                    this.offHoursState.mappingTotalGridToFoldedGridSubColumns.set(
                        count * cellPart + i,
                        index * cellPart + i
                    );
                }
                if (foldedColumns[count] && unit === "week") {
                    this.offHoursState.foldedColumns.push(1);
                } else {
                    this.offHoursState.foldedColumns.push(0);
                }
                count++;
            }
        }
        this.offHoursState.mappingTotalGridToFoldedGridSubColumns.set(
            this.columnCount * cellPart + 1,
            this.offHoursState.foldedGridColumnSpans.length * cellPart + 1
        );
        let colIndex = 0;
        this.offHoursState.mappingFoldedGridToTotalGridColumnIndex = new Map(
            this.offHoursState.foldedGridColumnSpans.map((val, gridIndex) => {
                const res = [gridIndex, colIndex];
                colIndex += val;
                return res;
            })
        );
    }

    toggleFoldableColumn(column, fold) {
        if (!this.offHoursState.foldedColumns) {
            this.offHoursState.foldedColumns = new Array(this.columnCount).fill(0);
        }
        const { startIndex, stopIndex } = this.foldableColumnsMapping[column.index];
        this.offHoursState.foldedColumns.fill(fold ? 1 : 0, startIndex, stopIndex + 1);
        this.computeFoldedGrid();
        this.cleanMultiSelection();
    }

    toggleCollapsableColumnHeaderHighlighting(collapsableColumnHeader) {
        if (
            !collapsableColumnHeader ||
            collapsableColumnHeader.classList.contains("o_gantt_header_folded")
        ) {
            const columnHeaders = this.gridRef.el.querySelectorAll(".o_gantt_foldable_hovered");
            for (const columnHeader of columnHeaders) {
                columnHeader.classList.remove("o_gantt_foldable_hovered");
            }
            return;
        }
        const columnHeaders = this.gridRef.el.querySelectorAll(".o_gantt_foldable");
        const foldableColumnsGroup =
            this.foldableColumnsMapping[+collapsableColumnHeader.dataset.columnIndex];
        for (const columnHeader of columnHeaders) {
            const columnIndex = +columnHeader.dataset.columnIndex;
            const currentGroup = this.foldableColumnsMapping[columnIndex];
            if (foldableColumnsGroup.foldableGroupNum === currentGroup.foldableGroupNum) {
                columnHeader.classList.add("o_gantt_foldable_hovered");
            } else {
                columnHeader.classList.remove("o_gantt_foldable_hovered");
            }
        }
    }

    initBadges(pill) {
        const { dateStartField, dateStopField } = this.model.metaData;
        const { record } = this.pills[pill.dataset.pillId];
        this.badgeInitialStartDate = record[dateStartField];
        this.badgeInitialStopDate = record[dateStopField];
    }

    updateBadges({ startBadge, stopBadge }) {
        Object.assign(this.timeDisplayBadgeReactiveStart, startBadge);
        Object.assign(this.timeDisplayBadgeReactiveStop, stopBadge);
    }

    clearBadges() {
        clearObject(this.timeDisplayBadgeReactiveStart);
        clearObject(this.timeDisplayBadgeReactiveStop);
        delete this.badgeInitialStartDate;
        delete this.badgeInitialStopDate;
    }

    //-------------------------------------------------------------------------
    // Handlers
    //-------------------------------------------------------------------------

    getSelectedRecordIds(selectedCells, predicate = () => true) {
        const ids = new Set();
        for (const selectedCell of selectedCells) {
            const recordsInSelectedCell = this.mappingCellToRecords[selectedCell];
            for (const record of recordsInSelectedCell || []) {
                if (predicate(record)) {
                    ids.add(record.id);
                }
            }
        }
        return [...ids];
    }

    onMultiDelete(selectedCells) {
        const ids = this.getSelectedRecordIds(selectedCells);
        return this.model.unlinkRecords(ids);
    }

    getCellsInBlock(block) {
        const { startCol, endCol, startRow, endRow } = block;
        const gridRowByFirstRow = {};
        for (const row of this.rows) {
            const gridRow = row.grid.row;
            const [first] = gridRow;
            if (first >= endRow) {
                break;
            }
            if (startRow <= first) {
                gridRowByFirstRow[first] = gridRow;
            }
        }
        const notFoldedCols = new Set();
        for (let col = startCol; col < endCol; col++) {
            const columnIndex = this.getColumnIndexFromColNumber(col);
            const isFolded = Boolean(this.offHoursState.foldedColumns?.[columnIndex]);
            if (!isFolded) {
                notFoldedCols.add(col);
            }
        }
        const cells = new Set();
        for (const gridRow of Object.values(gridRowByFirstRow)) {
            const subKey = `${gridRow[0]}_${gridRow[1]}`;
            for (const col of notFoldedCols) {
                cells.add(`${subKey}_${col}_${col + 1}`);
            }
        }
        return cells;
    }

    getBlock(selectedCell) {
        const [startRow, endRow, startCol, endCol] = selectedCell.split("_");
        return { startCol: +startCol, endCol: +endCol, startRow: +startRow, endRow: +endRow };
    }

    getCellsInfo(selectedCells) {
        const cellsInfo = [];
        const colsInfo = {};
        for (const selectedCell of selectedCells) {
            const { startRow, startCol } = this.getBlock(selectedCell);
            const rowId = this.rowIdsByFirstRow[startRow];
            if (!rowId) {
                continue;
            }
            if (!colsInfo[startCol]) {
                let { start, stop } = this.getSubColumnFromColNumber(startCol);
                ({ start, stop } = this.normalizeTimeRange(start, stop));
                colsInfo[startCol] = { start, stop };
            }
            const { start, stop } = colsInfo[startCol];
            cellsInfo.push({ rowId, start, stop });
        }
        return cellsInfo;
    }

    onMultiCreate(multiCreateData, selectedCells) {
        const cellsInfo = this.getCellsInfo(selectedCells);
        return this.model.multiCreateRecords(multiCreateData, cellsInfo);
    }

    onCellClicked(rowId, column, row) {
        const startCol = column.grid.column[0];
        if (this.model.hasMultiCreate) {
            if (column.isFolded) {
                return;
            }
            const endCol = startCol + this.model.metaData.scale.cellPart;
            const [startRow, endRow] = row;
            const block = { startCol, endCol, startRow, endRow };
            const action = this.ctrlPressed ? "toggle" : "replace";
            this.updateMultiSelection(block, action);
            this.drawCellGhosts(this.selectedCells);
            return;
        }
        if (!this.preventClick) {
            this.preventClick = true;
            setTimeout(() => (this.preventClick = false), 1000);
            if (column.isFolded) {
                this.toggleFoldableColumn(column, false);
                return;
            }
            const { canCellCreate, canPlan } = this.model.metaData;
            if (canPlan) {
                this.onPlan(rowId, startCol, startCol);
            } else if (canCellCreate) {
                this.onCreate(rowId, startCol, startCol + this.model.metaData.scale.cellPart - 1);
            }
        }
    }

    onCreate(rowId, startCol, stopCol, additionalContext = {}) {
        let { start } = this.getSubColumnFromColNumber(startCol);
        let { stop } = this.getSubColumnFromColNumber(stopCol);
        ({ start, stop } = this.normalizeTimeRange(start, stop));
        const context = this.model.getDialogContext({
            rowId,
            start,
            stop,
            withDefault: true,
        });
        this.props.create({
            ...context,
            ...additionalContext,
        });
    }

    normalizeTimeRange(start, stop) {
        stop = stop.plus({ second: 1 });
        return { start, stop };
    }

    onInteractionChange() {
        let { dragAction, mode } = this.interaction;
        if (mode === "drag") {
            mode = dragAction;
        }
        if (this.gridRef.el) {
            for (const [action, className] of INTERACTION_CLASSNAMES) {
                this.gridRef.el.classList.toggle(className, mode === action);
            }
        }
    }

    onPointerLeave() {
        this.throttledComputeHoverParams.cancel();

        if (!this.isDragging) {
            const hoveredConnectorId = this.hovered.connector?.dataset.connectorId;
            this.toggleConnectorHighlighting(hoveredConnectorId, false);

            this.toggleCollapsableColumnHeaderHighlighting(null);
        }

        this.hovered.connector = null;
        this.hovered.pill = null;
        this.hovered.hoverable = null;
        this.hovered.collapsableColumnHeader = null;

        this.computeDerivedParamsFromHover();
    }

    /**
     * Updates all hovered elements, then calls "computeDerivedParamsFromHover".
     *
     * @see computeDerivedParamsFromHover
     * @param {Event} ev
     */
    computeHoverParams(ev) {
        // Lazily compute elements from point as it is a costly operation
        let els = null;
        let position = {};
        if (ev.type === "scroll") {
            position = this.cursorPosition;
        } else {
            position.x = ev.clientX;
            position.y = ev.clientY;
            this.cursorPosition = position;
        }
        const pointedEls = () => els || (els = document.elementsFromPoint(position.x, position.y));

        // To find hovered elements, also from pointed elements
        const find = (selector) =>
            ev.target.closest?.(selector) ||
            pointedEls().find((el) => el.matches(selector)) ||
            null;

        this.hovered.connector = find(".o_gantt_connector");
        this.hovered.hoverable = find(".o_gantt_hoverable");
        this.hovered.pill = find(".o_gantt_pill_wrapper");
        this.hovered.collapsableColumnHeader = find(".o_gantt_foldable");

        this.computeDerivedParamsFromHover();
    }

    /**
     * @param {PointerEvent} ev
     * @param {Pill} pill
     */
    async onPillClicked(ev, pill) {
        if (this.popover.isOpen) {
            return;
        }
        const target = ev.target.closest(".o_gantt_pill_wrapper");
        const props = await this.keepLast.add(this.getPopoverProps(pill));
        this.popover.open(target, props);
    }

    onPlan(rowId, startCol, stopCol) {
        let { start, stop } = this.getColumnStartStop(startCol, stopCol);
        ({ start, stop } = this.normalizeTimeRange(start, stop));
        this.dialogService.add(
            SelectCreateDialog,
            this.getSelectCreateDialogProps({ rowId, start, stop, withDefault: true })
        );
    }

    getRecordIds(connectorId) {
        const { sourcePillId, targetPillId } = this.mappingConnectorToPills[connectorId];
        return {
            masterId: this.pills[sourcePillId]?.record.id,
            slaveId: this.pills[targetPillId]?.record.id,
        };
    }

    /**
     *
     * @param {Object} params
     * @param {ConnectorId} connectorId
     */
    onRemoveButtonClick(connectorId) {
        const { masterId, slaveId } = this.getRecordIds(connectorId);
        this.model.removeDependency(masterId, slaveId);
    }
    rescheduleAccordingToDependencyCallback(result) {
        const isWarning = result.type === "warning";
        if (!isWarning && "old_vals_per_pill_id" in result) {
            this.model.toggleHighlightPlannedFilter(
                Object.keys(result["old_vals_per_pill_id"]).map(Number)
            );
        }
        this.closeNotificationFn?.();
        const icon = isWarning ? "fa-warning" : "fa-check";
        this.closeNotificationFn = this.notificationService.add(
            markup`<i class="fa ${icon}"></i><span class="ms-1">${result["message"]}</span>`,
            {
                type: result["type"],
                sticky: true,
                buttons:
                    isWarning || !result.old_vals_per_pill_id
                        ? []
                        : [
                              {
                                  name: "Undo",
                                  icon: "fa-undo",
                                  onClick: async () => {
                                      const ids = Object.keys(result["old_vals_per_pill_id"]).map(
                                          Number
                                      );
                                      await this.orm.call(
                                          this.model.metaData.resModel,
                                          "action_rollback_scheduling",
                                          [ids, result["old_vals_per_pill_id"]]
                                      );
                                      this.closeNotificationFn();
                                      await this.model.fetchData();
                                  },
                              },
                          ],
            }
        );
    }

    /**
     * @param {KeyboardEvent} ev
     */
    onWindowKeyDown(ev) {
        if (ev.key === "Control") {
            this.prevDragAction =
                this.interaction.dragAction === "copy" ? "reschedule" : this.interaction.dragAction;
            this.interaction.dragAction = "copy";
            this.ctrlPressed = true;
        }
    }

    /**
     * @param {KeyboardEvent} ev
     */
    onWindowKeyUp(ev) {
        if (ev.key === "Control") {
            this.interaction.dragAction = this.prevDragAction || "reschedule";
            this.ctrlPressed = false;
        }
    }
}
