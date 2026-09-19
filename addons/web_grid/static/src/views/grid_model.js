import { KeepLast, Mutex } from "@web/core/utils/concurrency";
import { useService } from "@web/core/utils/hooks";
import { Domain } from "@web/core/domain";
import { serializeDate } from "@web/core/l10n/dates";
import { localization } from "@web/core/l10n/localization";
import { _t } from "@web/core/l10n/translation";
import { pyToJsLocale } from "@web/core/l10n/utils";
import { Model } from "@web/model/model";
import { browser } from "@web/core/browser/browser";

const { DateTime, Interval } = luxon;

export class GridCell {
    /**
     * Constructor
     *
     * @param model {GridModel} the grid model.
     * @param row {GridRow} the grid row linked to the cell.
     * @param column {GridColumn} the grid column linked to the cell.
     * @param value {Number} the value of the cell.
     * @param isHovered {Boolean} is the cell in a hover state?
     */
    constructor(model, row, column, value = 0, isHovered = false) {
        this.row = row;
        this.column = column;
        this.model = model;
        this.value = value;
        this.isHovered = isHovered;
        this._readonly = false;
        this.column.addCell(this);
    }

    get readonly() {
        return this._readonly || this.column.readonly;
    }

    /**
     * Get the domain of the cell, it will be the domain of row AND the one of the column associated
     *
     * @return {Domain} the domain of the cell
     */
    get domain() {
        const domains = [this.model.searchParams.domain, this.row.domain, this.column.domain];
        return Domain.and(domains);
    }

    /**
     * Get the context to get the default values
     */
    get context() {
        return {
            ...(this.model.searchParams.context || {}),
            ...this.row.section?.context,
            ...this.row.context,
            ...this.column.context,
        };
    }

    get title() {
        const rowTitle =
            !this.row.section || this.row.section.isFake
                ? this.row.title
                : `${this.row.section.title} / ${this.row.title}`;
        const columnTitle = this.column.title;
        return `${rowTitle} (${columnTitle})`;
    }

    /**
     * Update the grid cell according to the value set by the current user.
     *
     * @param {Number} value the value entered by the current user.
     */
    async update(value) {
        return this.model.mutex.exec(async () => {
            await this._update(value);
        });
    }

    async _update(value) {
        const oldValue = this.value;
        const result = await this.model.orm.call(
            this.model.resModel,
            "grid_update_cell",
            [this.domain.toList({}), this.model.measureFieldName, value - oldValue],
            { context: this.context }
        );
        if (result) {
            this.model.actionService.doAction(result);
            return;
        }
        this.row.updateCell(this.column, value, this.model.data);
        this.model.notify();
    }
}

export class GridRow {
    /**
     * Constructor
     *
     * @param domain {Domain} the domain of the row.
     * @param valuePerFieldName {{string: string}} the list of to display the label of the row.
     * @param model {GridModel} the grid model.
     * @param section {GridSection} the section of the grid.
     * @param columns {GridColumn[]} the columns of the grid.
     */
    constructor(data, domain, valuePerFieldName, model, section, isAdditionalRow = false) {
        this._domain = domain;
        this.model = model;
        this.cells = {};
        this.valuePerFieldName = valuePerFieldName;
        this.id = model.rowId++;
        this.section = section;
        if (section) {
            this.section.addRow(this);
        }
        this.grandTotal = 0;
        this.grandTotalWeekendHidden = 0;
        this.isAdditionalRow = isAdditionalRow;
        this._generateCells(data);
    }

    get initialRecordValues() {
        return this.valuePerFieldName;
    }

    get title() {
        const labelArray = [];
        for (const rowField of this.model.rowFields) {
            let title = this.valuePerFieldName[rowField.name];
            if (this.model.fieldsInfo[rowField.name].type === "many2one") {
                if (title) {
                    title = title[1];
                } else if (labelArray.length) {
                    title = "";
                } else {
                    title = "None";
                }
            }
            if (title) {
                labelArray.push(title);
            }
        }
        return labelArray.join(" / ");
    }

    get domain() {
        if (this.section.isFake) {
            return this._domain;
        }
        return Domain.and([this.section.domain, this._domain]);
    }

    get context() {
        const context = {};
        const getValue = (fieldName, value) =>
            this.model.fieldsInfo[fieldName].type === "many2one" ? value && value[0] : value;
        for (const [key, value] of Object.entries(this.valuePerFieldName)) {
            context[`default_${key}`] = getValue(key, value);
        }
        return context;
    }

    getSection() {
        return !this.section.isFake && this.section;
    }

    /**
     * Generate the cells for each column that is present in the row.
     * @private
     */
    _generateCells(data) {
        for (const column of Object.values(data.columns)) {
            this.cells[column.id] = new this.model.constructor.Cell(this.model, this, column, 0);
        }
    }

    _ensureColumnExist(column, data) {
        if (!(column.id in data.columns)) {
            throw new Error("Unbound index: the columnId is not in the row columns");
        }
        return true;
    }

    /**
     * Update the cell value of a cell.
     * @param {GridColumn} column containing the cell to update.
     * @param {number} value the value to update
     */
    updateCell(column, value, data) {
        this._ensureColumnExist(column, data);
        const cell = this.cells[column.id];
        const oldValue = cell.value;
        cell.value = value;
        const delta = value - oldValue;
        this.section.updateGrandTotal(column, delta);
        this.grandTotal += delta;
        this.grandTotalWeekendHidden += column.isWeekDay ? delta : 0;
        column.grandTotal += delta;
        if (this.isAdditionalRow && delta > 0) {
            this.isAdditionalRow = false;
        }
    }

    setReadonlyCell(column, readonly, data) {
        this._ensureColumnExist(column, data);
        if (readonly instanceof Array) {
            readonly = readonly.length > 0;
        } else if (!(readonly instanceof Boolean)) {
            readonly = Boolean(readonly);
        }
        this.cells[column.id]._readonly = readonly;
    }

    getGrandTotal(showWeekend) {
        return showWeekend ? this.grandTotal : this.grandTotalWeekendHidden;
    }
}

export class GridSection extends GridRow {
    constructor() {
        super(...arguments);
        this.sectionId = this.model.sectionId++;
        this.rows = {};
        this.isSection = true;
        this.lastRow = null;
    }

    get value() {
        return this.valuePerFieldName && this.valuePerFieldName[this.model.sectionField.name];
    }

    get domain() {
        let value = this.value;
        if (this.model.fieldsInfo[this.model.sectionField.name].type === "many2one") {
            value = value && value[0];
        }
        return new Domain([[this.model.sectionField.name, "=", value]]);
    }

    get title() {
        let title = this.value;
        if (
            this.model.sectionField &&
            this.model.fieldsInfo[this.model.sectionField.name].type === "many2one"
        ) {
            title = (title && title[1]) || "None";
        }
        return title;
    }

    get initialRecordValues() {
        return { [this.model.sectionField.name]: this.value };
    }

    get isFake() {
        return this.value == null;
    }

    get context() {
        const context = {};
        const getValue = (fieldName, value) =>
            this.model.fieldsInfo[fieldName].type === "many2one" ? value && value[0] : value;

        if (!this.isFake) {
            const sectionFieldName = this.model.sectionField.name;
            context[`default_${sectionFieldName}`] = getValue(sectionFieldName, this.value);
        }
        return context;
    }

    getSection() {
        return !this.isFake && this;
    }

    /**
     * Add row to the section rows.
     * @param row {GridRow} the row to add.
     */
    addRow(row) {
        if (row.id in this.rows) {
            throw new Error("Row already added in section");
        }
        this.rows[row.id] = row;
        this.lastRow = row;
    }

    /**
     * Update the grand totals according to the provided column and delta.
     * @param column {GridColumn} the column the grand total has to be updated for.
     * @param delta {Number} the delta to apply on the grand totals.
     */
    updateGrandTotal(column, delta) {
        this.cells[column.id].value += delta;
        this.grandTotal += delta;
        this.grandTotalWeekendHidden += column.isWeekDay ? delta : 0;
    }
}

export class GridColumn {
    /**
     * Constructor
     *
     * @param model {GridModel} the grid model.
     * @param title {string} the title of the column to display.
     */
    constructor(model, title, value, readonly = false) {
        this.model = model;
        this.title = title;
        this.value = value;
        this.cells = [];
        this.id = model.columnId++;
        this.grandTotal = 0;
        this.readonly = readonly;
    }

    /**
     * Add the cell to the column cells.
     * @param cell {GridCell} the cell to add.
     */
    addCell(cell) {
        if (cell.id in this.cells) {
            throw new Error("Cell already added in column");
        }
        this.cells.push(cell);
        this.grandTotal += cell.value;
    }

    get domain() {
        return new Domain([[this.model.columnFieldName, "=", this.value]]);
    }

    get context() {
        return { [`default_${this.model.columnFieldName}`]: this.value };
    }
}

export class DateGridColumn extends GridColumn {
    /**
     * Constructor
     *
     * @param model {GridModel} the grid model.
     * @param title {string} the title of the column to display.
     * @param dateStart {String} the date start serialized
     * @param dateEnd {String} the date end serialized
     * @param isToday {Boolean} is the date column representing today?
     */
    constructor(model, title, dateStart, dateEnd, isToday, isWeekDay, readonly = false) {
        super(model, title, dateStart, readonly);
        this.dateEnd = dateEnd;
        this.isToday = isToday;
        this.isWeekDay = isWeekDay;
    }

    get domain() {
        return new Domain([
            "&",
            [this.model.columnFieldName, ">=", this.value],
            [this.model.columnFieldName, "<", this.dateEnd],
        ]);
    }
}

export class GridNavigationInfo {
    constructor(anchor, model) {
        this.anchor = anchor;
        this.model = model;
    }

    get _targetWeekday() {
        const firstDayOfWeek = localization.weekStart;
        return this.anchor.weekday < firstDayOfWeek ? firstDayOfWeek - 7 : firstDayOfWeek;
    }

    get periodStart() {
        if (this.range.span !== "week") {
            return this.anchor.startOf(this.range.span);
        }
        // Luxon's default is monday to monday week so we need to change its behavior.
        return this.anchor.set({ weekday: this._targetWeekday }).startOf("day");
    }

    get periodEnd() {
        if (this.range.span !== "week") {
            return this.anchor.endOf(this.range.span);
        }
        // Luxon's default is monday to monday week so we need to change its behavior.
        return this.anchor
            .set({ weekday: this._targetWeekday })
            .plus({ weeks: 1, days: -1 })
            .endOf("day");
    }

    get interval() {
        return Interval.fromDateTimes(this.periodStart, this.periodEnd);
    }

    contains(date) {
        return this.interval.contains(date.startOf("day"));
    }
}

export class GridModel extends Model {
    static Cell = GridCell;
    static Column = GridColumn;
    static DateColumn = DateGridColumn;
    static Row = GridRow;
    static Section = GridSection;
    static NavigationInfo = GridNavigationInfo;

    setup(params) {
        this.notificationService = useService("notification");
        this.actionService = useService("action");
        this.keepLast = new KeepLast();
        this.mutex = new Mutex();
        this.defaultSectionField = params.sectionField;
        this.defaultRowFields = params.rowFields;
        this.sectionField = undefined;
        this.rowFields = [];
        this.searchParams = {};
        this.resModel = params.resModel;
        this.fieldsInfo = params.fieldsInfo;
        this.columnFieldName = params.columnFieldName;
        this.columnFieldIsDate = this.fieldsInfo[params.columnFieldName].type === "date";
        this.measureField = params.measureField;
        this.readonlyField = params.readonlyField;
        this.ranges = params.ranges;
        this.defaultAnchor = params.defaultAnchor || this.today;
        this.navigationInfo = new this.constructor.NavigationInfo(this.defaultAnchor, this);
        this.data = undefined;
        this.record = undefined;
        const activeRangeName =
            browser.localStorage.getItem(this.storageKey) || params.activeRangeName;
        if (Object.keys(this.ranges).length && activeRangeName) {
            this.navigationInfo.range = this.ranges[activeRangeName];
        }
        this._resetGridComponentsId();
    }

    get aggregates() {
        const aggregates = [this.measureGroupByFieldName, "id:array_agg"];
        if (this.readonlyField) {
            aggregates.push(`${this.readonlyField.name}:${this.readonlyField.aggregator}`);
        }
        return aggregates;
    }

    get today() {
        return DateTime.local().startOf("day");
    }

    get sectionsArray() {
        return Object.values(this.data.sections);
    }

    get rowsArray() {
        return Object.values(this.data.rows);
    }

    get columnsArray() {
        return Object.values(this.data.columns);
    }

    get itemsArray() {
        return this.data.items;
    }

    get maxColumnsTotal() {
        return Math.max(...this.columnsArray.map((c) => c.grandTotal));
    }

    get measureFieldName() {
        return this.measureField.name;
    }

    get measureGroupByFieldName() {
        if (this.measureField.aggregator) {
            return `${this.measureFieldName}:${this.measureField.aggregator}`;
        }
        return this.measureFieldName;
    }

    get storageKey() {
        return `scaleOf-viewId-${this.env.config.viewId}`;
    }

    get columnGroupByFieldName() {
        let columnGroupByFieldName = this.columnFieldName;
        if (this.columnFieldIsDate) {
            columnGroupByFieldName += `:${this.navigationInfo.range.step}`;
        }
        return columnGroupByFieldName;
    }

    isToday(date) {
        return date.startOf("day").equals(this.today.startOf("day"));
    }

    /**
     * Get fields to use in the group by or in fields of the read_group
     * @private
     * @params {Object} metaData
     * @return {string[]} list of fields name.
     */
    _getGroupByFields({ rowFields, sectionField } = this.metaData) {
        const fields = [this.columnGroupByFieldName, ...rowFields.map((r) => r.name)];
        if (sectionField) {
            fields.push(sectionField.name);
        }
        return fields;
    }

    _getDateColumnTitle(date) {
        const granularity = this.navigationInfo.range.step;
        if (!["day", "month"].includes(granularity)) {
            return serializeDate(date);
        }
        const locale = pyToJsLocale(this.navigationInfo.anchor.locale);

        const options = {
            day: { weekday: "short", month: "short", day: "numeric" },
            month: { month: "long", year: "numeric" },
        }[granularity];

        const parts = new Intl.DateTimeFormat(locale, options).formatToParts(date);

        const splitAfter = granularity === "day" ? "weekday" : "month";

        let splitIndex = parts.findIndex((p) => p.type === splitAfter);
        if (splitIndex === -1) {
            return parts.map((p) => p.value).join("");
        }

        // split after the first literal
        while (++splitIndex < parts.length) {
            if (parts[splitIndex].type === "literal") {
                break;
            }
        }

        const firstLineParts = parts.slice(0, splitIndex + 1);
        const secondLineParts = parts.slice(splitIndex + 1);

        const firstLine = firstLineParts
            .map((p) => p.value)
            .join("")
            .trim();
        const secondLine = secondLineParts
            .map((p) => p.value)
            .join("")
            .trim();
        return `${firstLine}\n${secondLine}`;
    }

    /**
     * @override
     */
    hasData() {
        return this.sectionsArray.length;
    }

    /**
     * Set the new range according to the range name passed into parameter.
     * @param rangeName {string} the range name to set.
     */
    async setRange(rangeName) {
        this.navigationInfo.range = this.ranges[rangeName];
        browser.localStorage.setItem(this.storageKey, rangeName);
        await this.reload();
    }

    async setAnchor(anchor) {
        this.navigationInfo.anchor = anchor;
        await this.reload();
    }

    async setTodayAnchor() {
        await this.setAnchor(this.today);
    }

    generateNavigationDomain() {
        if (this.columnFieldIsDate) {
            const { periodStart, periodEnd } = this.navigationInfo;
            return new Domain([
                "&",
                [this.columnFieldName, ">=", serializeDate(periodStart)],
                [this.columnFieldName, "<=", serializeDate(periodEnd)],
            ]);
        } else {
            return Domain.TRUE;
        }
    }

    /**
     * Reset the anchor
     */
    async resetAnchor() {
        await this.setAnchor(this.defaultAnchor);
    }

    /**
     * Move the anchor to the next/previous step
     * @param direction {"forward"|"backward"} the direction to the move the anchor
     */
    async moveAnchor(direction) {
        if (direction == "forward") {
            this.navigationInfo.anchor = this.navigationInfo.anchor.plus({
                [this.navigationInfo.range.span]: 1,
            });
        } else if (direction == "backward") {
            this.navigationInfo.anchor = this.navigationInfo.anchor.minus({
                [this.navigationInfo.range.span]: 1,
            });
        } else {
            throw Error("Invalid argument");
        }
        if (
            this.navigationInfo.contains(this.today) &&
            this.navigationInfo.anchor.startOf("day").equals(this.today.startOf("day"))
        ) {
            this.navigationInfo.anchor = this.today;
        }
        await this.reload();
    }

    async loadData(metaData) {
        this._resetGridComponentsId();
        Object.assign(metaData, await this._getInitialData(metaData));
        const { data, sectionField } = metaData;

        const mergeAdditionalData = (fetchedData) => {
            const additionalData = {};
            for (const fetchedDatum of fetchedData) {
                for (const [sectionKey, sectionInfo] of Object.entries(fetchedDatum)) {
                    if (!(sectionKey in additionalData)) {
                        additionalData[sectionKey] = sectionInfo;
                    } else {
                        for (const [rowKey, rowInfo] of Object.entries(sectionInfo.rows)) {
                            if (!(rowKey in additionalData[sectionKey].rows)) {
                                additionalData[sectionKey].rows[rowKey] = rowInfo;
                            }
                        }
                    }
                }
            }
            return additionalData;
        };

        const appendAdditionData = (additionalData) => {
            for (const [sectionKey, sectionInfo] of Object.entries(additionalData)) {
                if (!(sectionKey in data.sectionsKeyToIdMapping)) {
                    if (sectionField) {
                        const newSection = new this.constructor.Section(
                            data,
                            null,
                            { [sectionField.name]: sectionInfo.value },
                            this,
                            null
                        );
                        data.sections[newSection.id] = newSection;
                        data.sectionsKeyToIdMapping[sectionKey] = newSection.id;
                        data.rows[newSection.id] = newSection;
                        data.rowsKeyToIdMapping[sectionKey] = newSection.id;
                    } else {
                        // if no sectionField and the section is not in sectionsKeyToIdMapping then no section is generated
                        this._generateFakeSection(data);
                    }
                }
                const section = data.sections[data.sectionsKeyToIdMapping[sectionKey]];
                for (const [rowKey, rowInfo] of Object.entries(sectionInfo.rows)) {
                    if (!(rowKey in data.rowsKeyToIdMapping)) {
                        const newRow = new this.constructor.Row(
                            data,
                            rowInfo.domain,
                            rowInfo.values,
                            this,
                            section,
                            true
                        );
                        data.rows[newRow.id] = newRow;
                        data.rowsKeyToIdMapping[rowKey] = newRow.id;
                        for (const column of Object.values(data.columns)) {
                            newRow.updateCell(column, 0, data);
                        }
                    }
                }
            }
        };

        const [dataFetched, additionalDataFetched] = await Promise.all([
            this.fetchData(metaData),
            Promise.all(this._fetchAdditionalData(metaData)),
        ]);
        this._generateData(dataFetched, metaData);
        appendAdditionData(mergeAdditionalData(additionalDataFetched));
        if (!this.orm.isSample) {
            const [, postFetchAdditionalData] = await Promise.all([
                Promise.all(this._getAdditionalPromises(metaData)),
                Promise.all(this._postFetchAdditionalData(metaData)),
            ]);
            appendAdditionData(mergeAdditionalData(postFetchAdditionalData));
        }

        const { items } = data;
        for (const section of Object.values(data.sections)) {
            items.push(section);
            this._itemsPostProcess(section, metaData);
            for (const rowId in section.rows) {
                const row = section.rows[rowId];
                this._itemsPostProcess(row, metaData);
                items.push(row);
            }
        }
    }

    /**
     * Load the model
     *
     * @override
     * @param params {Object} the search parameters (domain, groupBy, etc.)
     * @return {Promise<void>}
     */
    async load(params = {}) {
        const searchParams = {
            ...this.searchParams,
            ...params,
        };
        const groupBys = [];
        let notificationDisplayed = false;
        for (const groupBy of searchParams.groupBy) {
            if (groupBy.startsWith(this.columnFieldName)) {
                if (!notificationDisplayed) {
                    this.notificationService.add(
                        _t(
                            "Grouping by the field used in the column of the grid view is not possible."
                        ),
                        { type: "warning" }
                    );
                    notificationDisplayed = true;
                }
            } else {
                groupBys.push(groupBy);
            }
        }
        if (searchParams.length !== groupBys.length) {
            searchParams.groupBy = groupBys;
        }
        let rowFields = [];
        let sectionField;
        if (searchParams.groupBy.length) {
            if (
                this.defaultSectionField &&
                searchParams.groupBy.length > 1 &&
                searchParams.groupBy[0] === this.defaultSectionField.name
            ) {
                sectionField = this.defaultSectionField;
            }
            const rowFieldPerFieldName = Object.fromEntries(
                this.defaultRowFields.map((r) => [r.name, r])
            );
            for (const groupBy of searchParams.groupBy) {
                if (sectionField && groupBy === sectionField.name) {
                    continue;
                }
                if (groupBy in rowFieldPerFieldName) {
                    rowFields.push({
                        ...rowFieldPerFieldName[groupBy],
                        invisible: "False",
                    });
                } else {
                    rowFields.push({ name: groupBy });
                }
            }
        } else {
            if (
                this.defaultSectionField &&
                this.defaultSectionField.invisible !== "True" &&
                this.defaultSectionField.invisible !== "1"
            ) {
                sectionField = this.defaultSectionField;
            }
            rowFields = this.defaultRowFields.filter(
                (r) => r.invisible !== "True" && r.invisible !== "1"
            );
        }

        const metaData = {
            searchParams,
            rowFields,
            sectionField,
        };
        await this.keepLast.add(this.loadData(metaData));
        Object.assign(this, {
            ...metaData,
        });
    }

    async reload(params = {}) {
        await this.load(params);
        this.useSampleModel = false;
        this.notify();
    }

    /**
     * Generate the date columns.
     * @private
     * @return {GridColumn[]}
     */
    _generateDateColumns({ data }) {
        const generateNext = (dateStart) =>
            dateStart.plus({ [`${this.navigationInfo.range.step}s`]: 1 });
        for (
            let currentDate = this.navigationInfo.periodStart;
            currentDate < this.navigationInfo.periodEnd;
            currentDate = generateNext(currentDate)
        ) {
            const domainStart = currentDate;
            const domainStop = generateNext(currentDate);
            const domainStartSerialized = serializeDate(domainStart);
            const isWeekDay = currentDate.weekday < 6;
            const column = new this.constructor.DateColumn(
                this,
                this._getDateColumnTitle(currentDate),
                domainStartSerialized,
                serializeDate(domainStop),
                currentDate.startOf("day").equals(this.today.startOf("day")),
                isWeekDay
            );
            data.columns[column.id] = column;
            data.columnsKeyToIdMapping[domainStartSerialized] = column.id;
        }
    }

    /**
     * Search grid columns
     *
     * @param {Array} domain domain to filter the result
     * @param {string} readonlyField field uses to make column readonly if true
     * @returns {Array} array containing id, display_name and readonly if readonlyField is defined.
     */
    async _searchMany2oneColumns(domain, readonlyField) {
        const fieldsToFetch = ["id", "display_name"];
        if (readonlyField) {
            fieldsToFetch.push(readonlyField);
        }
        const columnField = this.fieldsInfo[this.columnFieldName];
        const columnRecords = await this.orm.searchRead(
            columnField.relation,
            domain || [],
            fieldsToFetch
        );
        return columnRecords.map((read) => Object.values(read));
    }

    /**
     * Initialize the data.
     * @private
     */
    async _getInitialData(metaData) {
        const initialData = {
            data: {
                columnsKeyToIdMapping: {},
                columns: {},
                rows: {},
                rowsKeyToIdMapping: {},
                fieldsInfo: this.fieldsInfo,
                sections: {},
                sectionsKeyToIdMapping: {},
                items: [],
            },
            record: {
                context: {},
                resModel: this.resModel,
                resIds: [],
            },
        };
        let columnRecords = [];
        const columnField = this.fieldsInfo[this.columnFieldName];
        if (this.columnFieldIsDate) {
            this._generateDateColumns(initialData);
        } else {
            if (columnField.type === "selection") {
                const selectionFieldValues = await this.orm.call(
                    "ir.model.fields",
                    "get_field_selection",
                    [this.resModel, this.columnFieldName]
                );
                columnRecords = selectionFieldValues;
            } else if (columnField.type === "many2one") {
                columnRecords = await this._searchMany2oneColumns();
            } else {
                throw new Error(
                    "Unmanaged column type. Supported types are date, selection and many2one."
                );
            }
            for (const record of columnRecords) {
                let readonly = false;
                let key, value;
                if (record.length === 2) {
                    [key, value] = record;
                } else {
                    [key, value, readonly] = record;
                }
                const column = new this.constructor.Column(this, value, key, Boolean(readonly));
                initialData.data.columns[column.id] = column;
                initialData.data.columnsKeyToIdMapping[key] = column.id;
            }
        }
        return initialData;
    }

    async fetchData(metaData) {
        const { searchParams } = metaData;
        let dataFetched = await this.orm.formattedReadGroup(
            this.resModel,
            Domain.and([searchParams.domain, this.generateNavigationDomain()]).toList({}),
            this._getGroupByFields(metaData),
            this.aggregates,
        );
        if (this.orm.isSample) {
            dataFetched = dataFetched.filter((group) => {
                const date = DateTime.fromISO(group[this.columnGroupByFieldName][0]);
                const { periodStart, periodEnd } = this.navigationInfo;
                return date >= periodStart && date <= periodEnd;
            });
        }
        return dataFetched;
    }

    /**
     * Gets additional groups to be added to the grid. The call to this function is made in parallel to the main data
     * fetching.
     *
     * This function is intended to be overriden in modules where we want to display additional sections and/or rows in
     * the grid than what would be returned by the formattedReadGroup.
     * The model `sectionField` and `rowFields` can be used in order to know what need to be returned.
     *
     * An example of this is:
     * - when considering timesheet, we want to ease their encoding by adding (to the data that is fetched for scale),
     *   the entries that have been entered the week before. That way, the first day of week
     *   (or month, depending on the scale), a line is already displayed with 0's and can directly been used in the
     *   grid instead of having to use the create button.
     *
     * @return {Array<Promise<Object>>} an array of Promise of Object of type:
     *                                      {
     *                                          sectionKey: {
     *                                              value: Any,
     *                                              rows: {
     *                                                  rowKey: {
     *                                                      domain: Domain,
     *                                                      values: [Any],
     *                                                  },
     *                                              },
     *                                          },
     *                                      }
     * @private
     */
    _fetchAdditionalData(metaData) {
        return [];
    }

    /**
     * Gets additional groups to be added to the grid. The call to this function is made after the main data fetching
     * has been processed which allows using `data` in the code.
     * This function is intended to be overriden in modules where we want to display additional sections and/or rows in
     * the grid than what would be returned by the formattedReadGroup.
     * The model `sectionField`, `rowFields` as well as `data` can be used in order to know what need to be returned.
     *
     * @return {Array<Promise<Object>>} an array of Promise of Object of type:
     *                                      {
     *                                          sectionKey: {
     *                                              value: Any,
     *                                              rows: {
     *                                                  rowKey: {
     *                                                      domain: Domain,
     *                                                      values: [Any],
     *                                                  },
     *                                              },
     *                                          },
     *                                      }
     * @private
     */
    _postFetchAdditionalData(metaData) {
        return [];
    }

    _getAdditionalPromises(metaData) {
        return [this._fetchUnavailabilityDays(metaData)];
    }

    async _fetchUnavailabilityDays(metaData, args = {}) {
        if (!this.columnFieldIsDate) {
            return {};
        }
        const result = await this.orm.call(
            this.resModel,
            "grid_unavailability",
            [
                serializeDate(this.navigationInfo.periodStart),
                serializeDate(this.navigationInfo.periodEnd),
            ],
            {
                ...args,
            }
        );
        this._processUnavailabilityDays(result);
    }

    _processUnavailabilityDays(result) {
        return;
    }

    /**
     * Generate the row key according to the provided read group result.
     * @param readGroupResult {Array} the read group result the key has to be generated for.
     * @private
     * @return {string}
     */
    _generateRowKey(readGroupResult, { sectionField, rowFields }) {
        let key = "";
        const sectionKey =
            (sectionField && this._generateSectionKey(readGroupResult, sectionField)) || false;
        for (const rowField of rowFields) {
            let value = rowField.name in readGroupResult && readGroupResult[rowField.name];
            if (this.fieldsInfo[rowField.name].type === "many2one") {
                value = value && value[0];
            }
            key += `${value}\\|/`;
        }
        return `${sectionKey}@|@${key}`;
    }

    /**
     * Generate the section
     * @param readGroupResult
     * @private
     */
    _generateSectionKey(readGroupResult, sectionField) {
        let value = readGroupResult[sectionField.name];
        if (this.fieldsInfo[sectionField.name].type === "many2one") {
            value = value && value[0];
        }
        return `/|\\${value.toString()}`;
    }

    /**
     * Generate the row domain for the provided read group result.
     * @param readGroupResult {Array} the read group result the domain has to be generated for.
     * @return {{domain: Domain, values: Object}} the generated domain and values.
     */
    _generateRowDomainAndValues(readGroupResult, rowFields) {
        let domain = new Domain();
        const values = {};
        for (const rowField of rowFields) {
            const result = rowField.name in readGroupResult && readGroupResult[rowField.name];
            let value = result;
            if (this.fieldsInfo[rowField.name].type === "many2one") {
                value = value && value[0];
            }
            values[rowField.name] = result;
            domain = Domain.and([domain, [[rowField.name, "=", value]]]);
        }
        return { domain, values };
    }

    _generateFakeSection(data) {
        const section = new this.constructor.Section(data, null, null, this, null);
        data.sections[section.id] = section;
        data.sectionsKeyToIdMapping["false"] = section.id;
        data.rows[section.id] = section;
        data.rowsKeyToIdMapping["false"] = section.id;
        return section;
    }

    async _generateData(readGroupResults, metaData) {
        const { data, record, sectionField, rowFields } = metaData;
        let section;
        for (const readGroupResult of readGroupResults) {
            if (!this.orm.isSample) {
                record.resIds.push(...readGroupResult['id:array_agg']);
            }
            const rowKey = this._generateRowKey(readGroupResult, metaData);
            if (sectionField) {
                const sectionKey = this._generateSectionKey(readGroupResult, sectionField);
                if (!(sectionKey in data.sectionsKeyToIdMapping)) {
                    const newSection = new this.constructor.Section(
                        data,
                        null,
                        { [sectionField.name]: readGroupResult[sectionField.name] },
                        this,
                        null
                    );
                    data.sections[newSection.id] = newSection;
                    data.sectionsKeyToIdMapping[sectionKey] = newSection.id;
                    data.rows[newSection.id] = newSection;
                    data.rowsKeyToIdMapping[sectionKey] = newSection.id;
                }
                section = data.sections[data.sectionsKeyToIdMapping[sectionKey]];
            } else if (Object.keys(data.sections).length === 0) {
                section = this._generateFakeSection(data);
            }
            let row;
            if (!(rowKey in data.rowsKeyToIdMapping)) {
                const { domain, values } = this._generateRowDomainAndValues(
                    readGroupResult,
                    rowFields
                );
                row = new this.constructor.Row(data, domain, values, this, section);
                data.rows[row.id] = row;
                data.rowsKeyToIdMapping[rowKey] = row.id;
            } else {
                row = data.rows[data.rowsKeyToIdMapping[rowKey]];
            }
            let columnKey;
            const columnField = this.fieldsInfo[this.columnFieldName];
            if (this.columnFieldIsDate || columnField.type === "many2one") {
                columnKey = readGroupResult[this.columnGroupByFieldName][0];
            } else if (columnField.type === "selection") {
                columnKey = readGroupResult[this.columnGroupByFieldName];
            } else {
                throw new Error(
                    "Unmanaged column type. Supported types are date, selection and many2one."
                );
            }
            if (data.columnsKeyToIdMapping[columnKey] in data.columns) {
                const column = data.columns[data.columnsKeyToIdMapping[columnKey]];
                row.updateCell(column, readGroupResult[this.measureGroupByFieldName], data);
                const readonlyFieldAggregator = this.readonlyField && `${this.readonlyField.name}:${this.readonlyField.aggregator}`;
                if (readonlyFieldAggregator && readonlyFieldAggregator in readGroupResult) {
                    row.setReadonlyCell(column, readGroupResult[readonlyFieldAggregator], data);
                }
            }
        }
    }

    /**
     * Method meant to be overridden whenever an item (row and section) post process is needed.
     * @param item {GridSection|GridRow}
     */
    _itemsPostProcess(item, metaData) {}

    _resetGridComponentsId() {
        this.columnId = 0;
        this.rowId = 0;
        this.sectionId = 0;
    }
}
