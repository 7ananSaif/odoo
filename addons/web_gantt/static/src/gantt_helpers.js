import { onWillUnmount, status, useComponent, useEffect, useEnv } from "@odoo/owl";
import { getEndOfLocalWeek, getStartOfLocalWeek } from "@web/core/l10n/dates";
import { makePopover, usePopover } from "@web/core/popover/popover_hook";
import { makeDraggableHook } from "@web/core/utils/draggable_hook_builder_owl";
import { useService } from "@web/core/utils/hooks";
import { clamp } from "@web/core/utils/numbers";
import { isObject, pick, shallowEqual } from "@web/core/utils/objects";
import { closest as getClosest } from "@web/core/utils/ui";
import { GanttPopoverInDialog } from "./gantt_popover_in_dialog";

const { DateTime } = luxon;

/** @typedef {luxon.DateTime} DateTime */

/**
 * @param {number} target
 * @param {number[]} values
 * @returns {number}
 */
function closest(target, values) {
    return values.reduce(
        (prev, val) => (Math.abs(val - target) < Math.abs(prev - target) ? val : prev),
        Infinity
    );
}

/**
 * Adds a time diff to a date keeping the same value even if the offset changed
 * during the manipulation. This is typically needed with timezones using DayLight
 * Saving offset changes.
 *
 * @example dateAddFixedOffset(luxon.DateTime.local(), { hour: 1 });
 * @param {DateTime} date
 * @param {Record<string, number>} plusParams
 */
export function dateAddFixedOffset(date, plusParams) {
    const shouldApplyOffset = Object.keys(plusParams).some((key) =>
        /^(hour|minute|second)s?$/i.test(key)
    );
    const result = date.plus(plusParams);
    if (shouldApplyOffset) {
        const initialOffset = date.offset;
        const diff = initialOffset - result.offset;
        if (diff) {
            const adjusted = result.plus({ minute: diff });
            return adjusted.offset === initialOffset ? result : adjusted;
        }
    }
    return result;
}

export function diffColumn(col1, col2, unit) {
    return col2.diff(col1, unit).values[`${unit}s`];
}

export function localStartOf(date, unit) {
    return unit === "week" ? getStartOfLocalWeek(date) : date.startOf(unit);
}

export function localEndOf(date, unit) {
    return unit === "week" ? getEndOfLocalWeek(date) : date.endOf(unit);
}

/**
 * @param {number} cellPart
 * @param {(0 | 1)[]} subSlotUnavailabilities
 * @param {boolean} isToday
 * @returns {string | null}
 */
export function getCellColor(cellPart, subSlotUnavailabilities, isToday) {
    const sum = subSlotUnavailabilities.reduce((acc, d) => acc + d);
    if (!sum) {
        return null;
    }
    switch (cellPart) {
        case sum: {
            return `background-color:${getCellPartColor(sum, isToday)}`;
        }
        case 2: {
            const [c0, c1] = subSlotUnavailabilities.map((d) => getCellPartColor(d, isToday));
            return `background:linear-gradient(90deg,${c0}49%,${c1}50%)`;
        }
        case 4: {
            const [c0, c1, c2, c3] = subSlotUnavailabilities.map((d) =>
                getCellPartColor(d, isToday)
            );
            return `background:linear-gradient(90deg,${c0}24%,${c1}25%,${c1}49%,${c2}50%,${c2}74%,${c3}75%)`;
        }
    }
}

/**
 * @param {0 | 1} availability
 * @param {boolean} isToday
 * @returns {string}
 */
export function getCellPartColor(availability, isToday) {
    if (availability) {
        return "var(--Gantt__DayOff-background-color)";
    } else if (isToday) {
        return "var(--Gantt__DayOffToday-background-color)";
    } else {
        return "var(--Gantt__Day-background-color)";
    }
}

/**
 * @param {number | [number, string]} value
 * @returns {number}
 */
export function getColorIndex(value) {
    if (typeof value === "number") {
        return Math.round(value) % NB_GANTT_RECORD_COLORS;
    } else if (isObject(value)) {
        return value.id % NB_GANTT_RECORD_COLORS;
    }
    return 0;
}

/**
 * Intervals are supposed to intersect (intersection duration >= 1 milliseconds)
 *
 * @param {[DateTime, DateTime]} interval
 * @param {[DateTime, DateTime]} otherInterval
 * @returns {[DateTime, DateTime]}
 */
export function getIntersection(interval, otherInterval) {
    const [start, end] = interval;
    const [otherStart, otherEnd] = otherInterval;
    return [start >= otherStart ? start : otherStart, end <= otherEnd ? end : otherEnd];
}

/**
 * Computes intersection of a closed interval with a union of closed intervals ordered and disjoint
 * = a union of intersections
 *
 * @param {[DateTime, DateTime]} interval
 * @param {[DateTime, DateTime]} intervals
 * @returns {[DateTime, DateTime][]}
 */
export function getUnionOfIntersections(interval, intervals) {
    const [start, end] = interval;
    const intersecting = intervals.filter((otherInterval) => {
        const [otheStart, otherEnd] = otherInterval;
        return otherEnd > start && end > otheStart;
    });
    const len = intersecting.length;
    if (len === 0) {
        return [];
    }
    const union = [];
    const first = getIntersection(interval, intersecting[0]);
    union.push(first);
    if (len >= 2) {
        const last = getIntersection(interval, intersecting[len - 1]);
        union.push(...intersecting.slice(1, len - 1), last);
    }
    return union;
}

export function getHoveredCellPart(cell, pointerX, cellPart, rtl) {
    const rect = cell.getBoundingClientRect();
    const x = Math.floor(rect.x);
    const width = Math.floor(rect.width);
    let part = Math.floor((clamp(pointerX, x, x + width - 1) - x) / (width / cellPart));
    part = clamp(part, 0, cellPart - 1);
    if (rtl) {
        part = cellPart - 1 - part;
    }
    return part;
}

export function getClosestCell(ctx, rowId) {
    const { hoveredCell, pointer, ref, rtl, scale } = ctx;
    let { el: cell, part } = hoveredCell;
    if (!cell) {
        const selector = rowId
            ? `.o_gantt_cells .o_gantt_cell:not(.o_drag_hover)[data-row-id='${CSS.escape(rowId)}']`
            : `.o_gantt_cells .o_gantt_cell:not(.o_drag_hover)`;
        cell = getClosest(ref.el.querySelectorAll(selector), pointer);
        part = getHoveredCellPart(cell, pointer.x, scale.cellPart, rtl);
    }
    return { cell, part };
}

/**
 * @param {Object} params
 * @param {Ref<HTMLElement>} params.ref
 * @param {string} params.selector
 * @param {string} params.exception
 * @param {string} params.related
 * @param {string} params.className
 */
export function useMultiHover({ ref, selector, exception, related, className }) {
    /**
     * @param {HTMLElement} el
     */
    const findSiblings = (el) =>
        ref.el.querySelectorAll(
            related
                .map((attr) => `[${attr}='${el.getAttribute(attr).replace(/'/g, "\\'")}']`)
                .join("")
        );

    /**
     * @param {PointerEvent} ev
     */
    const onPointerEnter = (ev) => {
        if (!ev.target.classList.contains(exception)) {
            for (const sibling of findSiblings(ev.target)) {
                sibling.classList.add(...classList);
                classedEls.add(sibling);
            }
        }
    };

    /**
     * @param {PointerEvent} ev
     */
    const onPointerLeave = (ev) => {
        for (const sibling of findSiblings(ev.target)) {
            sibling.classList.remove(...classList);
            classedEls.delete(sibling);
        }
    };

    const classList = className.split(/\s+/g);
    const classedEls = new Set();

    useEffect(
        (...targets) => {
            if (targets.length) {
                for (const target of targets) {
                    target.addEventListener("pointerenter", onPointerEnter);
                    target.addEventListener("pointerleave", onPointerLeave);
                }
                return () => {
                    for (const el of classedEls) {
                        el.classList.remove(...classList);
                    }
                    classedEls.clear();
                    for (const target of targets) {
                        target.removeEventListener("pointerenter", onPointerEnter);
                        target.removeEventListener("pointerleave", onPointerLeave);
                    }
                };
            }
        },
        () => [...ref.el.querySelectorAll(selector)]
    );
}

const NB_GANTT_RECORD_COLORS = 12;

function getElementCenter(el) {
    const { x, y, width, height } = el.getBoundingClientRect();
    return {
        x: x + width / 2,
        y: y + height / 2,
    };
}

function getBadgesPositions(el, rtl) {
    const rect = el.getBoundingClientRect();
    const sideBarWidth = document.querySelector(".o_gantt_row_sidebar")?.offsetWidth || 0;
    const startPosition = {
        left: Math.max(rect.x, sideBarWidth),
        top: rect.top - 20,
    };
    const stopPosition = {
        top: rect.y + rect.height,
        right: clamp(
            document.body.offsetWidth - rect.x - rect.width,
            1,
            window.innerWidth - sideBarWidth
        ),
    };
    return {
        startPosition: rtl ? stopPosition : startPosition,
        stopPosition: rtl ? startPosition : stopPosition,
    };
}

function getBadgeText(date, diff, scale) {
    const { cellPart, time, unitDescription } = scale;
    let text;
    switch (time) {
        case "minute":
            text = date.toLocaleString(DateTime.TIME_SIMPLE);
            break;
        case "hour":
            text =
                cellPart > 1 ? date.toLocaleString(DateTime.DATETIME_SHORT) : date.toLocaleString();
            break;
        default:
            text = date.toLocaleString();
    }
    if (diff) {
        const prefix = diff > 0 ? "+" : "";
        text += ` (${prefix}${diff} ${unitDescription})`;
    }
    return text;
}

function getBadge(position, text, diff) {
    return {
        class: diff ? (diff > 0 ? "text-success" : "text-danger") : "",
        position,
        text,
    };
}

export function getBadges(
    el,
    [startDate, startDiff],
    [stopDate, stopDiff],
    { rtl, scale },
    showDiff = true
) {
    const { startPosition, stopPosition } = getBadgesPositions(el, rtl);
    const startBadge = getBadge(
        startPosition,
        getBadgeText(startDate, showDiff ? startDiff : 0, scale),
        startDiff
    );
    const stopBadge = getBadge(
        stopPosition,
        getBadgeText(stopDate, showDiff ? stopDiff : 0, scale),
        stopDiff
    );
    return { startBadge, stopBadge };
}

// Resizable hook handles

const HANDLE_CLASS_START = "o_handle_start";
const HANDLE_CLASS_END = "o_handle_end";
const handles = {
    start: document.createElement("div"),
    end: document.createElement("div"),
};

// Draggable hooks

export const useGanttConnectorDraggable = makeDraggableHook({
    name: "useGanttConnectorDraggable",
    acceptedParams: {
        parentWrapper: [String],
    },
    onComputeParams({ ctx, params }) {
        ctx.parentWrapper = params.parentWrapper;
        ctx.followCursor = false;
    },
    onDragStart: ({ ctx, addStyle }) => {
        const { current } = ctx;
        const parent = current.element.closest(ctx.parentWrapper);
        if (!parent) {
            return;
        }
        for (const otherParent of ctx.ref.el.querySelectorAll(ctx.parentWrapper)) {
            if (otherParent !== parent) {
                addStyle(otherParent, { pointerEvents: "auto" });
            }
        }
        return { sourcePill: parent, ...current.connectorCenter };
    },
    onDrag: ({ ctx }) => {
        ctx.current.connectorCenter = getElementCenter(ctx.current.element);
        return pick(ctx.current, "connectorCenter");
    },
    onDragEnd: ({ ctx }) => pick(ctx.current, "element"),
    onDrop: ({ ctx, target }) => {
        const { current } = ctx;
        const parent = current.element.closest(ctx.parentWrapper);
        const targetParent = target.closest(ctx.parentWrapper);
        if (!targetParent || targetParent === parent) {
            return;
        }
        return { target: targetParent };
    },
    onWillStartDrag: ({ ctx }) => {
        ctx.current.connectorCenter = getElementCenter(ctx.current.element);
        return {};
    },
});

function getCoordinate(style, name) {
    return +style.getPropertyValue(name).slice(1);
}

export function getColumnStart(style) {
    return getCoordinate(style, "grid-column-start");
}

export function getColumnEnd(style) {
    return getCoordinate(style, "grid-column-end");
}

function getRowStart(style) {
    return getCoordinate(style, "grid-row-start");
}

function getRowEnd(style) {
    return getCoordinate(style, "grid-row-end");
}

export const useGanttDraggable = makeDraggableHook({
    name: "useGanttDraggable",
    acceptedParams: {
        cells: [String, Function],
        cellDragClassName: [String, Function],
        ghostClassName: [String, Function],
        hoveredCell: [Object],
        addStickyCoordinates: [Function],
        rtl: [Boolean, Function],
        scale: [Object, Function],
        getBadgesInitialDates: [Function],
    },
    onComputeParams({ ctx, params }) {
        ctx.cellSelector = params.cells;
        ctx.ghostClassName = params.ghostClassName;
        ctx.cellDragClassName = params.cellDragClassName;
        ctx.hoveredCell = params.hoveredCell;
        ctx.addStickyCoordinates = params.addStickyCoordinates;
        ctx.scale = params.scale;
        ctx.getBadgesInitialDates = params.getBadgesInitialDates;
        ctx.rtl = params.rtl;
    },
    onDragStart({ ctx }) {
        const { current, ghostClassName } = ctx;
        current.element.before(current.placeHolder);
        if (ghostClassName) {
            current.placeHolder.classList.add(ghostClassName);
        }
        return { pill: current.element };
    },
    onDrag({ ctx, addStyle }) {
        const { cellSelector, current, getBadgesInitialDates, hoveredCell, scale } = ctx;
        let { el: cell, part } = hoveredCell;

        const isDifferentCell = cell !== current.cell.el;
        const isDifferentPart = part !== current.cell.part;

        if (cell && !cell.matches(cellSelector)) {
            cell = null; // Not a cell
        }
        if (cell && cell.classList.contains("o_gantt_cell_folded")) {
            return;
        }

        current.cell.el = cell;
        current.cell.part = part;

        if (cell) {
            // Recompute cell style if in a different cell
            if (isDifferentCell) {
                const style = getComputedStyle(cell);
                current.cell.gridRow = style.getPropertyValue("grid-row");
                current.cell.gridColumnStart = getColumnStart(style) + current.gridColumnOffset;
            }
            // Assign new grid coordinates if in different cell or different cell part
            if (isDifferentCell || isDifferentPart) {
                const { pillSpan } = current;
                const { gridRow, gridColumnStart: start } = current.cell;
                const gridColumnStart = clamp(start + part, 1, current.maxGridColumnStart);
                const gridColumnEnd = gridColumnStart + pillSpan;
                current.diff = gridColumnStart - current.initialCol;

                addStyle(current.cellGhost, {
                    gridRow,
                    gridColumn: `c${gridColumnStart} / c${gridColumnEnd}`,
                });

                const [gridRowStart, gridRowEnd] = /r(\d+) \/ r(\d+)/g.exec(gridRow).slice(1);
                ctx.addStickyCoordinates(
                    [gridRowStart, gridRowEnd],
                    [gridColumnStart, gridColumnEnd]
                );
                current.cell.col = gridColumnStart;
            }
        } else {
            current.cell.col = null;
        }

        // Attach or remove cell ghost
        if (isDifferentCell) {
            if (cell) {
                cell.after(current.cellGhost);
            } else {
                current.cellGhost.remove();
            }
        }
        const { cellTime, time } = scale;
        const { start, stop } = getBadgesInitialDates();
        const diff = current.diff * cellTime;
        const startDate = dateAddFixedOffset(start, { [time]: diff });
        const stopDate = dateAddFixedOffset(stop, { [time]: diff });
        return getBadges(current.element, [startDate, diff], [stopDate, diff], ctx, false);
    },
    onDragEnd({ ctx }) {
        return { pill: ctx.current.element };
    },
    onDrop({ ctx }) {
        const { cellSrc, cell, element, initialCol } = ctx.current;
        if (cell.col !== null) {
            return {
                pill: element,
                cellSrc: cellSrc,
                cellDst: cell.el,
                diff: cell.col - initialCol,
            };
        }
    },
    onWillStartDrag({ ctx, addCleanup, addClass }) {
        const { current } = ctx;
        const { el: cell, part } = ctx.hoveredCell;

        current.placeHolder = current.element.cloneNode(true);
        current.cellGhost = document.createElement("div");
        current.cellGhost.className = ctx.cellDragClassName;
        current.cell = { el: null, index: null, part: 0 };
        current.cellSrc = cell;

        const gridStyle = getComputedStyle(cell.parentElement);
        const pillStyle = getComputedStyle(current.element);
        const cellStyle = getComputedStyle(cell);

        const gridTemplateColumns = gridStyle.getPropertyValue("grid-template-columns");
        const pGridColumnStart = getColumnStart(pillStyle);
        const pGridColumnEnd = getColumnEnd(pillStyle);
        const cGridColumnStart = getColumnStart(cellStyle) + part;

        let highestGridCol;
        for (const e of gridTemplateColumns.split(/\s+/).reverse()) {
            const res = /\[c(\d+)\]/g.exec(e);
            if (res) {
                highestGridCol = +res[1];
                break;
            }
        }

        const pillSpan = pGridColumnEnd - pGridColumnStart;

        current.initialCol = pGridColumnStart;
        current.diff = 0;
        current.maxGridColumnStart = highestGridCol - pillSpan;
        current.gridColumnOffset = pGridColumnStart - cGridColumnStart;
        current.pillSpan = pillSpan;

        addClass(ctx.ref.el, "pe-auto");
        addCleanup(() => {
            current.placeHolder.remove();
            current.cellGhost.remove();
        });
        return {};
    },
});

export const useGanttUndraggable = makeDraggableHook({
    name: "useGanttUndraggable",
    onDragStart({ ctx }) {
        return { pill: ctx.current.element };
    },
    onDragEnd({ ctx }) {
        return { pill: ctx.current.element };
    },
    onWillStartDrag({ ctx, addCleanup, addClass, addStyle, getRect }) {
        const { x, y, width, height } = getRect(ctx.current.element);
        ctx.current.container = document.createElement("div");

        addClass(ctx.ref.el, "pe-auto");
        addStyle(ctx.current.container, {
            position: "fixed",
            left: `${x}px`,
            top: `${y}px`,
            width: `${width}px`,
            height: `${height}px`,
        });

        ctx.current.element.after(ctx.current.container);
        addCleanup(() => ctx.current.container.remove());
        return {};
    },
});

export const useGanttResizable = makeDraggableHook({
    name: "useGanttResizable",
    requiredParams: ["handles"],
    acceptedParams: {
        innerPills: [String, Function],
        handles: [String, Function],
        hoveredCell: [Object],
        rtl: [Boolean, Function],
        cells: [String, Function],
        scale: [Object, Function],
        getBadgesInitialDates: [Function],
        showHandles: [Function],
    },
    onComputeParams({ ctx, params, addCleanup, addEffectCleanup, getRect }) {
        const onElementPointerEnter = (ev) => {
            if (ctx.dragging || ctx.willDrag) {
                return;
            }

            const pill = ev.target;
            const innerPill = pill.querySelector(params.innerPills);

            const pillRect = getRect(innerPill);

            for (const el of Object.values(handles)) {
                el.style.height = `${pillRect.height}px`;
            }

            const showHandles = params.showHandles ? params.showHandles(pill) : {};
            if ("start" in showHandles && !showHandles.start) {
                handles.start.remove();
            } else {
                innerPill.appendChild(handles.start);
            }
            if ("end" in showHandles && !showHandles.end) {
                handles.end.remove();
            } else {
                innerPill.appendChild(handles.end);
            }
        };

        const onElementPointerLeave = () => {
            const remove = () => Object.values(handles).forEach((h) => h.remove());
            if (ctx.dragging || ctx.current.element) {
                addCleanup(remove);
            } else {
                remove();
            }
        };

        ctx.hoveredCell = params.hoveredCell;
        ctx.scale = params.scale;
        ctx.getBadgesInitialDates = params.getBadgesInitialDates;
        ctx.rtl = params.rtl;

        for (const el of ctx.ref.el.querySelectorAll(params.elements)) {
            el.addEventListener("pointerenter", onElementPointerEnter);
            el.addEventListener("pointerleave", onElementPointerLeave);
            addEffectCleanup(() => {
                el.removeEventListener("pointerenter", onElementPointerEnter);
                el.removeEventListener("pointerleave", onElementPointerLeave);
            });
        }

        handles.start.className = `${params.handles} ${HANDLE_CLASS_START}`;
        handles.start.style.cursor = `${params.rtl ? "e" : "w"}-resize`;

        handles.end.className = `${params.handles} ${HANDLE_CLASS_END}`;
        handles.end.style.cursor = `${params.rtl ? "w" : "e"}-resize`;

        // Override "full" and "element" selectors: we want the draggable feature
        // to apply to the handles
        ctx.pillSelector = ctx.elementSelector;
        ctx.fullSelector = ctx.elementSelector = `.${params.handles}`;

        // Force the handles to stay in place
        ctx.followCursor = false;
    },
    onDragStart({ ctx, addStyle }) {
        addStyle(ctx.current.pill, { zIndex: 15 });
        return { pill: ctx.current.pill };
    },
    onDrag({ ctx, addStyle, getRect }) {
        const { getBadgesInitialDates, current, scale, pointer, rtl } = ctx;
        const { cell, part } = getClosestCell(ctx, ctx.current.rowId);
        if (cell.classList.contains("o_gantt_cell_folded")) {
            return;
        }
        const cellStyle = getComputedStyle(cell);
        const cGridColStart = getColumnStart(cellStyle);

        const { x, width } = getRect(cell);
        const coef = ((rtl ? -1 : 1) * width) / scale.cellPart;
        const startBorder = (rtl ? x + width : x) + part * coef;
        const endBorder = startBorder + coef;

        const theClosest = closest(pointer.x, [startBorder, endBorder]);

        let diff =
            cGridColStart +
            part +
            (theClosest === startBorder ? 0 : 1) -
            (current.isStart ? current.firstCol : current.lastCol);

        if (diff === current.lastDiff) {
            return;
        }

        if (current.isStart) {
            diff = Math.min(diff, current.initialDiff - 1);
            addStyle(current.pill, { "grid-column-start": `c${current.firstCol + diff}` });
        } else {
            diff = Math.max(diff, 1 - current.initialDiff);
            addStyle(current.pill, { "grid-column-end": `c${current.lastCol + diff}` });
        }
        current.lastDiff = diff;

        const { cellTime, time } = scale;
        const startDiff = current.isStart ? -diff * cellTime : 0;
        const stopDiff = current.isStart ? 0 : diff * cellTime;
        const { start, stop } = getBadgesInitialDates();
        const startDate = current.isStart
            ? dateAddFixedOffset(start, {
                  [time]: diff * cellTime,
              })
            : start;
        const stopDate = current.isStart
            ? stop
            : dateAddFixedOffset(stop, {
                  [time]: diff * cellTime,
              });
        return getBadges(current.pill, [startDate, startDiff], [stopDate, stopDiff], ctx);
    },
    onDragEnd({ ctx }) {
        const { current, pillSelector } = ctx;
        const pill = current.element.closest(pillSelector);
        return { pill };
    },
    onDrop({ ctx }) {
        const { current } = ctx;

        if (!current.lastDiff) {
            return;
        }

        const direction = current.isStart ? "start" : "end";
        return { pill: current.pill, diff: current.lastDiff, direction };
    },
    onWillStartDrag({ ctx, addClass }) {
        const { current, hoveredCell, pillSelector } = ctx;

        const pill = ctx.current.element.closest(pillSelector);
        current.pill = pill;

        const pillStyle = getComputedStyle(pill);
        current.firstCol = getColumnStart(pillStyle);
        current.lastCol = getColumnEnd(pillStyle);
        current.initialDiff = current.lastCol - current.firstCol;

        const { el: cell } = hoveredCell;
        current.rowId = cell.dataset.rowId;

        ctx.cursor = getComputedStyle(current.element).cursor;

        current.isStart = current.element.classList.contains(HANDLE_CLASS_START);

        addClass(ctx.ref.el, "pe-auto");
        return {};
    },
});

function getCellBounds({ cell, part }) {
    const startCol = +cell.dataset.col + part;
    const endCol = startCol + 1;
    const style = getComputedStyle(cell);
    const startRow = getRowStart(style);
    const endRow = getRowEnd(style);
    return { startCol, endCol, startRow, endRow };
}

function getBlockBounds(current) {
    const startCol = Math.min(current.initialCellBounds.startCol, current.cellBounds.startCol);
    const endCol = Math.max(current.initialCellBounds.endCol, current.cellBounds.endCol);
    const startRow = current.rowId
        ? current.initialCellBounds.startRow
        : Math.min(current.initialCellBounds.startRow, current.cellBounds.startRow);
    const endRow = current.rowId
        ? current.initialCellBounds.endRow
        : Math.max(current.initialCellBounds.endRow, current.cellBounds.endRow);
    return { startCol, endCol, startRow, endRow };
}

function getResult(current) {
    return { ...getBlockBounds(current), rowId: current.rowId };
}

/**
 * @param {HTMLElement} refEl: gantt grid
 * @param {string} rowId
 * @param {string} additionalSelector
 * @returns {cellEl[] | null}: cells found on the row that matched the selector
 */
export function getCellsOnRow(refEl, rowId, additionalSelector = "") {
    return refEl.querySelectorAll(
        `.o_gantt_cell${additionalSelector}[data-row-id='${CSS.escape(rowId)}']`
    );
}

export const useGanttSelectable = makeDraggableHook({
    name: "useGanttSelectable",
    acceptedParams: {
        hoveredCell: [Object],
        hasMultiCreate: [Boolean, Function],
        rtl: [Boolean, Function],
        scale: [Object, Function],
    },
    onComputeParams({ ctx, params }) {
        ctx.followCursor = false;
        ctx.hoveredCell = params.hoveredCell;
        ctx.hasMultiCreate = params.hasMultiCreate;
        ctx.rtl = params.rtl;
        ctx.scale = params.scale;
    },
    onWillStartDrag({ addClass, ctx }) {
        const { current, hoveredCell, ref } = ctx;
        const { el: cell, part } = hoveredCell;
        const cellBounds = getCellBounds({ cell, part });
        current.initialCellBounds = cellBounds;
        current.cellBounds = cellBounds;
        current.rowId = ctx.hasMultiCreate ? null : cell.dataset.rowId;
        addClass(ref.el, "pe-auto");
        addClass(cell, "pe-auto");
        return getResult(current);
    },
    onDragStart({ ctx, removeClass }) {
        const { current } = ctx;
        // Useless on cells, annoying on pills
        removeClass(current.element, "o_dragged");
        return getResult(current);
    },
    onDrag({ ctx }) {
        const { current } = ctx;
        const { cell, part } = getClosestCell(ctx, current.rowId);
        if (cell.classList.contains("o_gantt_cell_folded")) {
            return;
        }
        const cellBounds = getCellBounds({ cell, part });
        if (shallowEqual(current.cellBounds, cellBounds)) {
            return;
        }
        current.cellBounds = cellBounds;
        return getResult(current);
    },
    onDrop({ ctx }) {
        const { current } = ctx;
        return getResult(current);
    },
});

/**
 * Same as usePopover, but replaces the popover by a dialog when display size is small.
 *
 * @param {typeof import("@odoo/owl").Component} component
 * @param {import("@web/core/popover/popover_service").PopoverServiceAddOptions} [options]
 * @returns {import("@web/core/popover/popover_hook").PopoverHookReturnType}
 */
export function useGanttResponsivePopover(dialogTitle, component, options = {}) {
    const dialogService = useService("dialog");
    const env = useEnv();
    const owner = useComponent();
    const popover = usePopover(component, options);
    const onClose = () => {
        if (status(owner) !== "destroyed") {
            options.onClose?.();
        }
    };
    const dialogAddFn = (_, comp, props, options) => dialogService.add(comp, props, options);
    const popoverInDialog = makePopover(dialogAddFn, GanttPopoverInDialog, { onClose });
    const ganttReponsivePopover = {
        open: (target, props) => {
            if (env.isSmall) {
                popoverInDialog.open(target, {
                    component: component,
                    componentProps: props,
                    dialogTitle,
                });
            } else {
                popover.open(target, props);
            }
        },
        close: () => {
            popover.close();
            popoverInDialog.close();
        },
        get isOpen() {
            return popover.isOpen || popoverInDialog.isOpen;
        },
    };
    onWillUnmount(ganttReponsivePopover.close);
    return ganttReponsivePopover;
}
