import { browser } from "@web/core/browser/browser";
import { Domain } from "@web/core/domain";
import {
    deserializeDate,
    deserializeDateTime,
    serializeDate,
    serializeDateTime,
} from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { x2ManyCommands } from "@web/core/orm_service";
import { registry } from "@web/core/registry";
import { groupBy, unique } from "@web/core/utils/arrays";
import { KeepLast, Mutex } from "@web/core/utils/concurrency";
import { pick } from "@web/core/utils/objects";
import { Model } from "@web/model/model";
import { parseServerValue } from "@web/model/relational_model/utils";
import { formatFloatTime, formatPercentage } from "@web/views/fields/formatters";
import { getScaleForCustomRange } from "./gantt_arch_parser";
import { localStartOf } from "./gantt_helpers";

const { DateTime } = luxon;

/**
 * @typedef {luxon.DateTime} DateTime
 * @typedef {`[{${string}}]`} RowId
 * @typedef {import("./gantt_arch_parser").Scale} Scale
 * @typedef {import("./gantt_arch_parser").ScaleId} ScaleId
 *
 * @typedef ConsolidationParams
 * @property {string} excludeField
 * @property {string} field
 * @property {string} [maxField]
 * @property {string} [maxValue]
 *
 * @typedef Data
 * @property {Record<string, any>[]} records
 * @property {Row[]} rows
 *
 * @typedef Field
 * @property {string} name
 * @property {string} type
 * @property {[any, string][]} [selection]
 *
 * @typedef MetaData
 * @property {ConsolidationParams} consolidationParams
 * @property {string} dateStartField
 * @property {string} dateStopField
 * @property {string[]} decorationFields
 * @property {ScaleId} defaultRange
 * @property {string} dependencyField
 * @property {boolean} dependencyEnabled
 * @property {DateTime} stopDate
 *
 * @property {Scale} scale
 * @property {Scale[]} scales
 * @property {DateTime} startDate
 * @property {DateTime} stopDate
 *
 * @property {string} defaultRescheduleMethod
 * @property {string} rescheduleMethod
 * @property {Object[]} rescheduleMethods
 *
 * @typedef ProgressBar
 * @property {number} value_formatted
 * @property {number} max_value_formatted
 * @property {number} ratio
 * @property {string} warning
 *
 * @typedef Row
 * @property {RowId} id
 * @property {boolean} consolidate
 * @property {boolean} fromServer
 * @property {string[]} groupedBy
 * @property {string} groupedByField
 * @property {number} groupLevel
 * @property {string} name
 * @property {number[]} recordIds
 * @property {ProgressBar} [progressBar]
 * @property {number | false} resId
 * @property {Row[]} [rows]
 */

function firstColumnBefore(date, unit) {
    return localStartOf(date, unit);
}

function firstColumnAfter(date, unit) {
    const start = localStartOf(date, unit);
    if (date.equals(start)) {
        return date;
    }
    return start.plus({ [unit]: 1 });
}

/**
 * @param {Record<string, Field>} fields
 * @param {Record<string, any>} values
 */
export function parseServerValues(fields, values) {
    /** @type {Record<string, any>} */
    const parsedValues = {};
    if (!values) {
        return parsedValues;
    }
    for (const fieldName in values) {
        parsedValues[fieldName] = parseServerValue(fields[fieldName], values[fieldName]);
    }
    return parsedValues;
}

export class GanttModel extends Model {
    static services = ["notification"];

    setup(params, services) {
        this.notification = services.notification;

        /** @type {Data} */
        this.data = {};
        /** @type {MetaData} */
        this.metaData = params.metaData;
        this.displayParams = params.displayParams;

        this.searchParams = null;

        /** @type {Set<RowId>} */
        this.closedRows = new Set();

        // concurrency management
        this.keepLast = new KeepLast();
        this.mutex = new Mutex();
        /** @type {MetaData | null} */
        this._nextMetaData = null;
    }

    /**
     * @param {SearchParams} searchParams
     */
    async load(searchParams) {
        this.searchParams = searchParams;

        const metaData = this._buildMetaData();

        const params = {
            groupedBy: this._getGroupedBy(metaData, searchParams),
            pagerOffset: 0,
        };

        if (!metaData.scale || !metaData.startDate || !metaData.stopDate) {
            Object.assign(
                params,
                this._getInitialRangeParams(this._buildMetaData(params), searchParams)
            );
        }

        if (this.metaData.dependencyEnabled) {
            Object.assign(params, this._getInitialRescheduleMethod(this._buildMetaData(params)));
        }

        await this._fetchData(this._buildMetaData(params));
    }

    //-------------------------------------------------------------------------
    // Public
    //-------------------------------------------------------------------------

    get hasMultiCreate() {
        return (
            !!this.metaData.multiCreateView &&
            !this.env.isSmall &&
            this.displayParams.displayMode === "dense" &&
            this.metaData.scale.interval === "day"
        );
    }

    get showMultiCreateTimeRange() {
        return !this.dateStartFieldIsDate() && !this.dateStopFieldIsDate();
    }

    collapseRows() {
        const collapse = (rows) => {
            for (const row of rows) {
                this.closedRows.add(row.id);
                if (row.rows) {
                    collapse(row.rows);
                }
            }
        };
        collapse(this.data.rows);
        this.notify();
    }

    /**
     * Create a copy of a task with defaults determined by schedule.
     *
     * @param {number} id
     * @param {Record<string, any>} schedule
     * @param {(result: any) => any} [callback]
     */
    copy(id, schedule, callback) {
        const { resModel } = this.metaData;
        const { context } = this.searchParams;
        const data = this._scheduleToData(schedule);
        return this.mutex.exec(async () => {
            const result = await this.orm.call(resModel, "copy", [[id]], {
                context,
                default: data,
            });
            if (callback) {
                callback(result[0]);
            }
            this.fetchData();
            return result[0];
        });
    }

    /**
     * Adds a dependency between masterId and slaveId (slaveId depends
     * on masterId).
     *
     * @param {number} masterId
     * @param {number} slaveId
     */
    async createDependency(masterId, slaveId) {
        const { dependencyField, resModel } = this.metaData;
        const writeCommand = {
            [dependencyField]: [x2ManyCommands.link(masterId)],
        };
        await this.mutex.exec(() => this.orm.write(resModel, [slaveId], writeCommand));
        await this.fetchData();
    }

    dateStartFieldIsDate(metaData = this.metaData) {
        return metaData?.fields[metaData.dateStartField].type === "date";
    }

    dateStopFieldIsDate(metaData = this.metaData) {
        return metaData?.fields[metaData.dateStopField].type === "date";
    }

    expandRows() {
        this.closedRows.clear();
        this.notify();
    }

    get rowsAreExpanded() {
        return this.closedRows.size === 0;
    }

    async fetchData(params) {
        await this._fetchData(this._buildMetaData(params));
        this.useSampleModel = false;
        this.notify();
    }

    /**
     * @param {Object} params
     * @param {RowId} [params.rowId]
     * @param {DateTime} [params.start]
     * @param {DateTime} [params.stop]
     * @param {boolean} [params.withDefault]
     * @returns {Record<string, any>}
     */
    getDialogContext(params) {
        /** @type {Record<string, any>} */
        const context = { ...this.getSchedule(params) };

        if (params.withDefault) {
            const { dateStartField, dateStopField } = this.metaData;
            for (const k in context) {
                context[`default_${k}`] = context[k];
                if (![dateStartField, dateStopField].includes(k)) {
                    context[`search_default_${k}`] = context[k];
                }
            }
        }

        return Object.assign({}, this.searchParams.context, context);
    }

    getRangeFromDate(rangeId, date) {
        // 3 periods of type rangeId centered at date
        const startDate = localStartOf(date, rangeId).minus({ [rangeId]: 1 });
        const stopDate = startDate.plus({ [rangeId]: 3 }).minus({ day: 1 });
        return { focusDate: date, startDate, stopDate, rangeId };
    }

    /**
     * @param {Object} params
     * @param {RowId} [params.rowId]
     * @param {DateTime} [params.start]
     * @param {DateTime} [params.stop]
     * @returns {Record<string, any>}
     */
    getSchedule({ rowId, start, stop } = {}) {
        const { dateStartField, dateStopField, fields, groupedBy } = this.metaData;

        /** @type {Record<string, any>} */
        const schedule = {};

        if (start) {
            schedule[dateStartField] = this.dateStartFieldIsDate()
                ? serializeDate(start)
                : serializeDateTime(start);
        }
        if (stop && dateStartField !== dateStopField) {
            schedule[dateStopField] = this.dateStopFieldIsDate()
                ? serializeDate(stop)
                : serializeDateTime(stop);
        }
        if (rowId) {
            const group = Object.assign({}, ...JSON.parse(rowId));
            for (const fieldName of groupedBy) {
                if (fieldName in group) {
                    const value = group[fieldName];
                    if (Array.isArray(value)) {
                        const { type } = fields[fieldName];
                        schedule[fieldName] = type === "many2many" ? [value[0]] : value[0];
                    } else {
                        schedule[fieldName] = value;
                    }
                }
            }
        }

        return schedule;
    }

    /**
     * @override
     * @returns {boolean}
     */
    hasData() {
        return Boolean(this.data.records.length);
    }

    /**
     * @param {RowId} rowId
     * @returns {boolean}
     */
    isClosed(rowId) {
        return this.closedRows.has(rowId);
    }

    async multiCreateRecords(multiCreateData, cellsInfo) {
        if (!cellsInfo.length) {
            return;
        }
        const records = [];
        const values = await multiCreateData.record.getChanges();
        const timeRange = multiCreateData.timeRange;
        for (const { start, stop, rowId } of cellsInfo) {
            const schedule = this.getSchedule(
                timeRange
                    ? {
                          start: start.set(timeRange.start.toObject()),
                          stop: start.set(timeRange.end.toObject()),
                          rowId,
                      }
                    : { start, stop, rowId }
            );
            records.push({ ...schedule, ...values });
        }
        await this.orm.create(this.metaData.resModel, records, {
            context: { ...this.searchParams.context, multi_create: true },
        });
        await this.fetchData();
    }

    async unlinkRecords(ids) {
        if (!ids.length) {
            return;
        }
        await this.orm.unlink(this.metaData.resModel, ids);
        await this.fetchData();
    }

    /**
     * Removes the dependency between masterId and slaveId (slaveId is no
     * more dependent on masterId).
     *
     * @param {number} masterId
     * @param {number} slaveId
     */
    async removeDependency(masterId, slaveId) {
        const { dependencyField, resModel } = this.metaData;
        const writeCommand = {
            [dependencyField]: [x2ManyCommands.unlink(masterId)],
        };
        await this.mutex.exec(() => this.orm.write(resModel, [slaveId], writeCommand));
        await this.fetchData();
    }

    /**
     * Removes from 'data' the fields holding the same value as the records targetted
     * by 'ids'.
     *
     * @template {Record<string, any>} T
     * @param {T} data
     * @param {number[]} ids
     * @returns {Partial<T>}
     */
    removeRedundantData(data, ids) {
        const records = this.data.records.filter((rec) => ids.includes(rec.id));
        if (!records.length) {
            return data;
        }

        /**
         *
         * @param {Record<string, any>} record
         * @param {Field} field
         */
        const isSameValue = (record, { name, type }) => {
            const recordValue = record[name];
            let newValue = data[name];
            if (Array.isArray(newValue)) {
                [newValue] = newValue;
            }
            if (type === "many2one") {
                return recordValue.id === newValue;
            } else if (type === "one2many") {
                return recordValue[0] === newValue;
            } else if (type === "many2many") {
                return recordValue.includes(newValue);
            } else if (type === "date") {
                return serializeDate(recordValue) === newValue;
            } else if (type === "datetime") {
                return serializeDateTime(recordValue) === newValue;
            } else {
                return recordValue === newValue;
            }
        };

        /** @type {Partial<T>} */
        const trimmed = { ...data };

        for (const fieldName in data) {
            const field = this.metaData.fields[fieldName];
            if (records.every((rec) => isSameValue(rec, field))) {
                // All the records already have the given value.
                delete trimmed[fieldName];
            }
        }

        return trimmed;
    }

    _getRescheduleData(ids, schedule) {
        if (!Array.isArray(ids)) {
            ids = [ids];
        }
        const allData = this._scheduleToData(schedule);
        return [ids, this.removeRedundantData(allData, ids), this._getRescheduleContext()];
    }

    /**
     * Reschedule a task to the given schedule.
     *
     * @param {number | number[]} ids
     * @param {Record<string, any>} schedule
     * @param {(result: any) => any} [callback]
     */
    async reschedule(ids, schedule, callback) {
        let data, context;
        [ids, data, context] = this._getRescheduleData(ids, schedule);
        return this.mutex.exec(async () => {
            try {
                const result = await this._reschedule(ids, data, context);
                if (callback) {
                    await callback(result);
                }
            } finally {
                this.fetchData();
            }
        });
    }

    async _reschedule(ids, data, context) {
        return this.orm.write(this.metaData.resModel, ids, data, {
            context,
        });
    }

    toggleHighlightPlannedFilter(ids) {}

    async rescheduleAccordingToDependency(ids, schedule, rescheduleAccordingToDependencyCallback) {
        const {
            dateStartField,
            dateStopField,
            dependencyField,
            dependencyInvertedField,
            resModel,
        } = this.metaData;

        let data;
        [ids, data] = this._getRescheduleData(ids, schedule);

        return await this.mutex.exec(async () => {
            try {
                const result = await this.orm.call(resModel, "web_gantt_reschedule", [
                    data,
                    this.metaData.rescheduleMethod,
                    ids,
                    dependencyField,
                    dependencyInvertedField,
                    dateStartField,
                    dateStopField,
                ]);
                if (rescheduleAccordingToDependencyCallback) {
                    await rescheduleAccordingToDependencyCallback(result);
                }
            } finally {
                this.fetchData();
            }
        });
    }

    /**
     * @param {string} rowId
     */
    toggleRow(rowId) {
        if (this.isClosed(rowId)) {
            this.closedRows.delete(rowId);
        } else {
            this.closedRows.add(rowId);
        }
        this.notify();
    }

    async toggleDisplayMode() {
        this.displayParams.displayMode =
            this.displayParams.displayMode === "dense" ? "sparse" : "dense";
        this.closedRows.clear();
        this.notify();
    }

    async updatePagerParams({ limit, offset }) {
        await this.fetchData({ pagerLimit: limit, pagerOffset: offset });
    }

    //-------------------------------------------------------------------------
    // Protected
    //-------------------------------------------------------------------------

    /**
     * Return a copy of this.metaData or of the last copy, extended with optional
     * params. This is useful for async methods that need to modify this.metaData,
     * but it can't be done in place directly for the model to be concurrency
     * proof (so they work on a copy and commit it at the end).
     *
     * @protected
     * @param {Object} params
     * @param {DateTime} [params.focusDate]
     * @param {DateTime} [params.startDate]
     * @param {DateTime} [params.stopDate]
     * @param {string[]} [params.groupedBy]
     * @param {ScaleId} [params.scaleId]
     * @returns {MetaData}
     */
    _buildMetaData(params = {}) {
        this._nextMetaData = { ...(this._nextMetaData || this.metaData) };

        if (params.groupedBy) {
            this._nextMetaData.groupedBy = params.groupedBy;
        }
        if (params.focusDate) {
            this._nextMetaData.focusDate = params.focusDate;
        }
        if (params.startDate) {
            this._nextMetaData.startDate = params.startDate;
        }
        if (params.stopDate) {
            this._nextMetaData.stopDate = params.stopDate;
        }
        if (params.rangeId) {
            browser.localStorage.setItem(this._getLocalStorageKey(), params.rangeId);
            this._nextMetaData.rangeId = params.rangeId;
            if (this._nextMetaData.rangeId !== "custom") {
                this._nextMetaData.scale = this._nextMetaData.scales[params.rangeId];
            }
        }
        if (params.rescheduleMethod) {
            browser.localStorage.setItem(
                this._getRescehduleMethodLocalStorageKey(),
                params.rescheduleMethod
            );
            this._nextMetaData.rescheduleMethod = params.rescheduleMethod;
        }

        if ("pagerLimit" in params) {
            this._nextMetaData.pagerLimit = params.pagerLimit;
        }
        if ("pagerOffset" in params) {
            this._nextMetaData.pagerOffset = params.pagerOffset;
        }

        if ("rangeId" in params || "startDate" in params || "stopDate" in params) {
            if (this._nextMetaData.rangeId === "custom") {
                this._nextMetaData.scale = getScaleForCustomRange(this._nextMetaData);
            }
            // we assume that scale, startDate, and stopDate are already set in this._nextMetaData

            let exchange = false;
            if (this._nextMetaData.startDate > this._nextMetaData.stopDate) {
                exchange = true;
                const temp = this._nextMetaData.startDate;
                this._nextMetaData.startDate = this._nextMetaData.stopDate;
                this._nextMetaData.stopDate = temp;
            }
            const { interval } = this._nextMetaData.scale;

            const rightLimit = this._nextMetaData.startDate.plus({ year: 10, day: -1 });
            if (this._nextMetaData.stopDate > rightLimit) {
                if (exchange) {
                    this._nextMetaData.startDate = this._nextMetaData.stopDate.minus({
                        year: 10,
                        day: -1,
                    });
                } else {
                    this._nextMetaData.stopDate = this._nextMetaData.startDate.plus({
                        year: 10,
                        day: -1,
                    });
                }
            }
            this._nextMetaData.globalStart = firstColumnBefore(
                this._nextMetaData.startDate,
                interval
            );
            this._nextMetaData.globalStop = firstColumnAfter(
                this._nextMetaData.stopDate.plus({ day: 1 }),
                interval
            );

            if (params.currentFocusDate) {
                this._nextMetaData.focusDate = params.currentFocusDate;
                if (this._nextMetaData.focusDate < this._nextMetaData.startDate) {
                    this._nextMetaData.focusDate = this._nextMetaData.startDate;
                } else if (this._nextMetaData.stopDate < this._nextMetaData.focusDate) {
                    this._nextMetaData.focusDate = this._nextMetaData.stopDate;
                }
            }
        }

        return this._nextMetaData;
    }

    /**
     * Fetches records to display (and groups if necessary).
     *
     * @protected
     * @param {MetaData} metaData
     * @param {Object} [additionalContext]
     */
    async _fetchData(metaData, additionalContext) {
        const { globalStart, globalStop, groupedBy, pagerLimit, pagerOffset, resModel, scale } =
            metaData;
        const context = {
            ...this.searchParams.context,
            group_by: groupedBy,
            ...additionalContext,
        };
        const domain = this._getDomain(metaData);
        const fields = this._getFields(metaData);
        const specification = {};
        for (const fieldName of fields) {
            specification[fieldName] = {};
            if (metaData.fields[fieldName].type === "many2one") {
                specification[fieldName].fields = { display_name: {} };
            }
        }

        const ganttData = await this.keepLast.add(
            this.orm.call(resModel, "get_gantt_data", [], {
                domain,
                groupby: groupedBy,
                read_specification: specification,
                scale: scale.unit,
                start_date: serializeDateTime(globalStart),
                stop_date: serializeDateTime(globalStop),
                unavailability_fields: this._getUnavailabilityFields(metaData),
                progress_bar_fields: this._getProgressBarFields(metaData),
                context,
                limit: pagerLimit,
                offset: pagerOffset,
            })
        );

        const { length, groups, records, progress_bars, unavailabilities } = ganttData;

        groups.forEach((g) => (g.fromServer = true));

        const data = { count: length };

        data.records = this._parseServerData(metaData, records);
        data.rows = this._generateRows(metaData, {
            groupedBy,
            groups,
            parentGroup: [],
        });
        data.unavailabilities = this._processUnavailabilities(unavailabilities);
        data.progressBars = this._processProgressBars(progress_bars);

        this._processGanttData(metaData, data, ganttData);

        if (JSON.stringify(this.metaData.groupedBy) !== JSON.stringify(groupedBy)) {
            this.closedRows.clear();
        }
        this.data = data;
        this.metaData = metaData;
        this._nextMetaData = null;
    }

    /**
     * @protected
     * @param {MetaData} metaData
     * @param {Data} data
     * @param {Object} ganttData
     */
    _processGanttData(metaData, data, ganttData) {}

    /**
     * Remove date in groupedBy field
     *
     * @protected
     * @param {MetaData} metaData
     * @param {string[]} groupedBy
     * @returns {string[]}
     */
    _filterDateIngroupedBy(metaData, groupedBy) {
        return groupedBy.filter((gb) => {
            const [fieldName] = gb.split(":");
            const { type } = metaData.fields[fieldName];
            return !["date", "datetime"].includes(type);
        });
    }

    /**
     * @protected
     * @param {number} floatVal
     * @param {string}
     */
    _formatTime(floatVal) {
        const timeStr = formatFloatTime(floatVal, { noLeadingZeroHour: true });
        const [hourStr, minuteStr] = timeStr.split(":");
        const hour = parseInt(hourStr, 10);
        const minute = parseInt(minuteStr, 10);
        return minute ? _t("%(hour)sh%(minute)s", { hour, minute }) : _t("%sh", hour);
    }

    /**
     * Process groups to generate a recursive structure according
     * to groupedBy fields. Note that there might be empty groups (filled by
     * read_goup with group_expand) that also need to be processed.
     *
     * @protected
     * @param {MetaData} metaData
     * @param {Object} params
     * @param {Object[]} params.groups
     * @param {string[]} params.groupedBy
     * @param {Object[]} params.parentGroup
     * @returns {Row[]}
     */
    _generateRows(metaData, params) {
        const groupedBy = params.groupedBy;
        const groups = params.groups;
        const groupLevel = metaData.groupedBy.length - groupedBy.length;
        const parentGroup = params.parentGroup;

        if (!groupedBy.length || !groups.length) {
            const recordIds = [];
            for (const g of groups) {
                recordIds.push(...(g.__record_ids || []));
            }
            const part = parentGroup.at(-1);
            const [[parentGroupedField, value]] = part ? Object.entries(part) : [[]];
            return [
                {
                    groupLevel,
                    id: JSON.stringify([...parentGroup, {}]),
                    name: "",
                    recordIds: unique(recordIds),
                    parentGroupedField,
                    parentResId: Array.isArray(value) ? value[0] : value,
                    __extra__: true,
                },
            ];
        }

        /** @type {Row[]} */
        const rows = [];

        // Some groups might be empty (thanks to expand_groups), so we can't
        // simply group the data, we need to keep all returned groups
        const groupedByField = groupedBy[0];
        const currentLevelGroups = groupBy(groups, (g) => {
            if (g[groupedByField] === undefined) {
                // we want to group the groups with undefined values for groupedByField with the ones
                // with false value for the same field.
                // we also want to be sure that stringification keeps groupedByField:
                // JSON.stringify({ key: undefined }) === "{}"
                // see construction of id below.
                g[groupedByField] = false;
            }
            return g[groupedByField];
        });
        const { maxField } = metaData.consolidationParams;
        const consolidate = groupLevel === 0 && groupedByField === maxField;
        const generateSubRow = maxField ? true : groupedBy.length > 1;
        for (const key in currentLevelGroups) {
            const subGroups = currentLevelGroups[key];
            const value = subGroups[0][groupedByField];
            const part = {};
            part[groupedByField] = value;
            const fakeGroup = [...parentGroup, part];
            const id = JSON.stringify(fakeGroup);
            const resId = Array.isArray(value) ? value[0] : value; // not really a resId
            const fromServer = subGroups.some((g) => g.fromServer);
            const recordIds = [];
            for (const g of subGroups) {
                recordIds.push(...(g.__record_ids || []));
            }
            const row = {
                consolidate,
                fromServer,
                groupedBy,
                groupedByField,
                groupLevel,
                id,
                name: this._getRowName(metaData, groupedByField, value),
                resId, // not really a resId
                recordIds: unique(recordIds),
            };
            if (generateSubRow) {
                row.rows = this._generateRows(metaData, {
                    ...params,
                    groupedBy: groupedBy.slice(1),
                    groups: subGroups,
                    parentGroup: fakeGroup,
                });
            }
            if (resId === false) {
                rows.unshift(row);
            } else {
                rows.push(row);
            }
        }

        return rows;
    }

    /**
     * Get domain of records to display in the gantt view.
     *
     * @protected
     * @param {MetaData} metaData
     * @returns {any[]}
     */
    _getDomain(metaData) {
        const { dateStartField, dateStopField, globalStart, globalStop } = metaData;
        const domain = Domain.and([
            this.searchParams.domain,
            [
                "&",
                [
                    dateStartField,
                    "<",
                    this.dateStopFieldIsDate(metaData)
                        ? serializeDate(globalStop)
                        : serializeDateTime(globalStop),
                ],
                [
                    dateStopField,
                    this.dateStartFieldIsDate(metaData) ? ">=" : ">",
                    this.dateStartFieldIsDate(metaData)
                        ? serializeDate(globalStart)
                        : serializeDateTime(globalStart),
                ],
            ],
        ]);
        return domain.toList();
    }

    /**
     * Format field value to display purpose.
     *
     * @protected
     * @param {any} value
     * @param {Object} field
     * @returns {string} formatted field value
     */
    _getFieldFormattedValue(value, field) {
        if (field.type === "boolean") {
            return value ? "True" : "False";
        } else if (!value) {
            return field.falsy_value_label || _t("Undefined %s", field.string);
        } else if (field.type === "many2many") {
            return value[1];
        }
        const formatter = registry.category("formatters").get(field.type);
        return formatter(value, field);
    }

    /**
     * Get all the fields needed.
     *
     * @protected
     * @param {MetaData} metaData
     * @returns {string[]}
     */
    _getFields(metaData) {
        const fields = new Set([
            "display_name",
            metaData.dateStartField,
            metaData.dateStopField,
            ...metaData.groupedBy,
            ...metaData.decorationFields,
        ]);
        if (metaData.colorField) {
            fields.add(metaData.colorField);
        }
        if (metaData.consolidationParams.field) {
            fields.add(metaData.consolidationParams.field);
        }
        if (metaData.consolidationParams.excludeField) {
            fields.add(metaData.consolidationParams.excludeField);
        }
        if (metaData.dependencyField) {
            fields.add(metaData.dependencyField);
        }
        if (metaData.progressField) {
            fields.add(metaData.progressField);
        }
        return [...fields];
    }

    /**
     * @protected
     * @param {MetaData} metaData
     * @param {{ groupBy: string[] }} searchParams
     * @returns {string[]}
     */
    _getGroupedBy(metaData, searchParams) {
        let groupedBy = [...searchParams.groupBy];
        groupedBy = groupedBy.filter((gb) => {
            const [fieldName] = gb.split(".");
            const field = metaData.fields[fieldName];
            return field?.type !== "properties";
        });
        return this._filterDateIngroupedBy(metaData, groupedBy);
    }

    _getDefaultFocusDate(searchParams) {
        const { context } = searchParams;
        const focusDate =
            "initialDate" in context ? deserializeDateTime(context.initialDate) : DateTime.local();
        return focusDate.startOf("day");
    }

    /**
     * @protected
     * @param {MetaData} metaData
     * @param {{ context: Record<string, any> }} searchParams
     * @returns {{ focusDate: DateTime, scaleId: ScaleId, startDate: DateTime, stopDate: DateTime }}
     */
    _getInitialRangeParams(metaData, searchParams) {
        const { context } = searchParams;
        const localRangeId = this._getRangeIdFromLocalStorage(metaData);

        const rangeFromContext = context.default_range || context.default_scale;
        let rangeId =
            localRangeId ||
            (rangeFromContext in metaData.ranges ? rangeFromContext : metaData.defaultRange);

        let focusDate;
        if (rangeId in metaData.ranges) {
            focusDate = this._getDefaultFocusDate(searchParams);
            return { ...this.getRangeFromDate(rangeId, focusDate) };
        }
        rangeId = "custom";
        let startDate = context.default_start_date && deserializeDate(context.default_start_date);
        let stopDate = context.default_stop_date && deserializeDate(context.default_stop_date);
        const defaultRangeCount = 3;
        const defaultRangeUnit = "month";
        if (!startDate && !stopDate) {
            /** @type {DateTime} */
            focusDate = this._getDefaultFocusDate(searchParams);
            startDate = firstColumnBefore(focusDate, defaultRangeUnit);
            stopDate = startDate.plus({ [defaultRangeUnit]: defaultRangeCount }).minus({ day: 1 });
        } else if (startDate && !stopDate) {
            const column = firstColumnBefore(startDate, defaultRangeUnit);
            focusDate = startDate;
            stopDate = column.plus({ [defaultRangeUnit]: defaultRangeCount }).minus({ day: 1 });
        } else if (!startDate && stopDate) {
            const column = firstColumnAfter(stopDate, defaultRangeUnit);
            focusDate = stopDate;
            startDate = column.minus({ [defaultRangeUnit]: defaultRangeCount });
        } else {
            focusDate = DateTime.local();
            if (focusDate < startDate) {
                focusDate = startDate;
            } else if (focusDate > stopDate) {
                focusDate = stopDate;
            }
        }

        return { focusDate, startDate, stopDate, rangeId };
    }

    _getLocalStorageKey() {
        return `rangeOf-viewId-${this.env.config.viewId}`;
    }

    _getProgressBarFields(metaData) {
        if (metaData.progressBarFields && !this.orm.isSample) {
            return metaData.progressBarFields.filter(
                (fieldName) =>
                    metaData.groupedBy.includes(fieldName) &&
                    ["many2many", "many2one"].includes(metaData.fields[fieldName]?.type)
            );
        }
        return [];
    }

    _getRescheduleContext() {
        return { ...this.searchParams.context };
    }

    /**
     * @protected
     * @param {MetaData} metaData
     * @param {string} groupedByField
     * @param {any} value
     * @returns {string}
     */
    _getRowName(metaData, groupedByField, value) {
        const field = metaData.fields[groupedByField];
        return this._getFieldFormattedValue(value, field);
    }

    _getRangeIdFromLocalStorage(metaData) {
        const { ranges } = metaData;
        const localRangeId = browser.localStorage.getItem(this._getLocalStorageKey());
        return localRangeId in ranges ? localRangeId : null;
    }

    _getInitialRescheduleMethod(metaData) {
        return {
            rescheduleMethod:
                this._getRescheduleMethodFromLocalStorage(metaData) ||
                metaData.defaultRescheduleMethod,
        };
    }

    _getRescehduleMethodLocalStorageKey() {
        return `rescheduleMethod-viewId-${this.env.config.viewId}`;
    }

    _getRescheduleMethodFromLocalStorage(metaData) {
        const { rescheduleMethods } = metaData;
        const localRescheduleMethod = browser.localStorage.getItem(
            this._getRescehduleMethodLocalStorageKey()
        );
        return localRescheduleMethod in rescheduleMethods ? localRescheduleMethod : null;
    }

    /**
     * @protected
     * @param {MetaData} metaData
     * @returns {string[]}
     */
    _getUnavailabilityFields(metaData) {
        if (metaData.displayUnavailability && !this.orm.isSample && metaData.groupedBy.length) {
            const lastGroupBy = metaData.groupedBy.at(-1);
            const { type } = metaData.fields[lastGroupBy] || {};
            if (["many2many", "many2one"].includes(type)) {
                return [lastGroupBy];
            }
        }
        return [];
    }

    /**
     * @protected
     * @param {MetaData} metaData
     * @param {Record<string, any>[]} records the server records to parse
     * @returns {Record<string, any>[]}
     */
    _parseServerData(metaData, records) {
        const { dateStartField, dateStopField, fields } = metaData;
        /** @type {Record<string, any>[]} */
        const parsedRecords = [];
        for (const record of records) {
            const parsedRecord = parseServerValues(fields, record);
            const dateStart = parsedRecord[dateStartField];
            const dateStop = parsedRecord[dateStopField];
            if (dateStart <= dateStop) {
                parsedRecords.push(parsedRecord);
            }
        }
        return parsedRecords;
    }

    _processProgressBar(progressBar, warning) {
        const processedProgressBar = {
            ...progressBar,
            value_formatted: this._formatTime(progressBar.value),
            max_value_formatted: this._formatTime(progressBar.max_value),
            ratio: progressBar.max_value ? (progressBar.value / progressBar.max_value) * 100 : 0,
            warning,
        };
        if (processedProgressBar?.max_value) {
            processedProgressBar.ratio_formatted = formatPercentage(
                processedProgressBar.ratio / 100
            );
        }
        return processedProgressBar;
    }

    _processProgressBars(progressBars) {
        const processedProgressBars = {};
        for (const fieldName in progressBars) {
            processedProgressBars[fieldName] = {};
            const progressBarInfo = progressBars[fieldName];
            for (const [resId, progressBar] of Object.entries(progressBarInfo)) {
                processedProgressBars[fieldName][resId] = this._processProgressBar(
                    progressBar,
                    progressBarInfo.warning
                );
            }
        }
        return processedProgressBars;
    }

    _processUnavailabilities(unavailabilities) {
        const processedUnavailabilities = {};
        for (const fieldName in unavailabilities) {
            processedUnavailabilities[fieldName] = {};
            for (const [resId, resUnavailabilities] of Object.entries(
                unavailabilities[fieldName]
            )) {
                processedUnavailabilities[fieldName][resId] = resUnavailabilities.map((u) => ({
                    start: deserializeDateTime(u.start),
                    stop: deserializeDateTime(u.stop),
                }));
            }
        }
        return processedUnavailabilities;
    }

    /**
     * @template {Record<string, any>} T
     * @param {T} schedule
     * @returns {Partial<T>}
     */
    _scheduleToData(schedule) {
        const allowedFields = [
            this.metaData.dateStartField,
            this.metaData.dateStopField,
            ...this.metaData.groupedBy,
        ];
        return pick(schedule, ...allowedFields);
    }
}
