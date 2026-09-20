import { serializeDate } from "@web/core/l10n/dates";
import { GridRow } from "@web_grid/views/grid_model";
import { TimesheetGridModel } from "../timesheet_grid/timesheet_grid_model";
import { user } from "@web/core/user";

export class TimerGridRow extends GridRow {
    constructor(data, domain, valuePerFieldName, model, section, isAdditionalRow = false) {
        super(data, domain, valuePerFieldName, model, section, isAdditionalRow);
        this.timerRunning = false;
    }

    async startTimer() {
        const vals = {};
        const getValue = (fieldName, value) =>
            this.model.fieldsInfo[fieldName].type === "many2one" ? value[0] : value;
        for (const [key, value] of Object.entries(this.valuePerFieldName)) {
            vals[key] = getValue(key, value);
        }
        if (!this.section.isFake) {
            vals[this.model.sectionField.name] = getValue(
                this.model.sectionField.name,
                this.section.value
            );
        }
        await this.model.startTimer(vals, this);
        this.timerRunning = true;
    }

    async stopTimer() {
        await this.model.stopTimer();
        this.timerRunning = false;
    }

    get timeData() {
        return {
            project_id: this.valuePerFieldName?.project_id?.[0],
            task_id: this.valuePerFieldName?.task_id?.[0],
        };
    }

    async addTime() {
        await this.model.addTime(this.timeData);
    }
}

export class TimerTimesheetGridModel extends TimesheetGridModel {
    static services = [...TimesheetGridModel.services, "timesheet_uom", "timesheet_timer"];
    static Row = TimerGridRow;

    setup(params, services) {
        super.setup(params, services);
        this.timesheetUOMService = services.timesheet_uom;
        this.timerService = services.timesheet_timer;
        this.fieldsInfo.project_id.required = "True";
    }

    get showTimer() {
        return this.timesheetUOMService.timesheetWidget === "float_time";
    }

    getTimesheetWorkingHoursPromises(metaData) {
        const promises = super.getTimesheetWorkingHoursPromises(metaData);
        promises.push(this.fetchDailyWorkingHours(metaData));
        return promises;
    }

    _setTimerData(timerData) {
        const { rowFields, sectionField, data } = this;
        this._updateTimer(timerData, { rowFields, sectionField, data });
    }

    async fetchDailyWorkingHours({ data }) {
        const { periodStart, periodEnd } = this.navigationInfo;
        const dailyWorkingHours = await this.orm.call("res.users", "get_daily_working_hours", [
            user.userId,
            serializeDate(periodStart),
            serializeDate(periodEnd),
        ]);
        data.workingHours.daily = dailyWorkingHours;
    }

    _getAdditionalPromises(metaData) {
        const promises = super._getAdditionalPromises(metaData);
        promises.push(this._getRunningTimer(metaData));
        return promises;
    }

    async _getInitialData(metaData) {
        const { sectionField, rowFields } = metaData;
        const initialData = await super._getInitialData(metaData);
        const { data } = initialData;
        data.workingHours.daily = {};
        data.rowPerKeyBinding = {};
        data.keyBindingPerRowId = {};
        data.stepTimer = 0;
        initialData.timerButtonIndex = 0;
        initialData.showTimerButtons =
            this.showTimer &&
            !sectionField &&
            rowFields.length &&
            rowFields.some((rowField) => rowField.name === "project_id");
        return initialData;
    }

    _itemsPostProcess(item, metaData) {
        super._itemsPostProcess(item, metaData);
        const { data, showTimerButtons } = metaData;
        if (!item.isSection && showTimerButtons) {
            if (metaData.timerButtonIndex < 26) {
                const timerButtonKey = String.fromCharCode(65 + metaData.timerButtonIndex++);
                data.rowPerKeyBinding[timerButtonKey] = item;
                data.keyBindingPerRowId[item.id] = timerButtonKey;
            }
        }
    }

    _updateTimer(timerData, metaData) {
        const { data } = metaData;
        if (!data.timer) {
            data.timer = timerData;
        } else {
            for (const [key, value] of Object.entries(timerData)) {
                data.timer[key] = value;
            }
        }
        if (data.timer.id) {
            // if the id linked to the timer changed then search the row associated
            this._searchRowWithTimer(metaData);
        }
    }

    _searchRowWithTimer({ sectionField, rowFields, data }) {
        let rowKey = `${sectionField ? data.timer[sectionField.name] : "false"}@|@`;
        for (const row of rowFields) {
            let value = data.timer[row.name];
            const fieldType = this.fieldsInfo[row.name].type;
            if (value && fieldType === "many2one") {
                if (value instanceof Array) {
                    value = value[0];
                } else {
                    value = value.id;
                }
            }
            rowKey += `${value}\\|/`;
        }
        if (rowKey in data.rowsKeyToIdMapping) {
            const row = data.rows[data.rowsKeyToIdMapping[rowKey]];
            row.timerRunning = true;
            if (data.timer.row) {
                data.timer.row.timerRunning = false;
            }
            data.timer.row = row;
        } else if (data.timer.row) {
            data.timer.row.timerRunning = false;
            delete data.timer.row;
        }
    }

    async _getRunningTimer(metaData) {
        const { data } = metaData;
        if (!this.showTimer) {
            return;
        }
        const { step_timer: stepTimer, ...timesheetWithTimerData } =
            await this.timerService.getRunningTimer();
        if (timesheetWithTimerData.id || timesheetWithTimerData.other_company) {
            this._updateTimer(timesheetWithTimerData, metaData);
        } else if (data.timer) {
            // remove running timer since there is no longer.
            if ("row" in data.timer) {
                data.timer.row.timerRunning = false;
            }
            delete data.timer;
        }
        data.stepTimer = stepTimer;
    }

    async startTimer(vals = {}, row = undefined) {
        const result = await this.timerService.startTimer(vals);
        const timesheetTimer = result || {};
        if (row) {
            timesheetTimer.row = row;
        }
        this._setTimerData(timesheetTimer || {});
    }

    /**
     * Update the timesheet in the timer header
     *
     * @param {import('@web/model/relational_model/record').Record} timesheet
     * @param {number} time the time representing in seconds to add to the timer of the timesheet
     */
    async updateTimerTimesheet(timesheetVals, time = 0.0) {
        this._setTimerData(timesheetVals);
        if (time) {
            return this.mutex.exec(async () => {
                await this.orm.call(this.resModel, "action_add_time_to_timer", [
                    timesheetVals.id,
                    time,
                ]);
            });
        }
    }

    async stopTimer() {
        const value = await this.timerService.stopTimer([true]);
        if (value) {
            const column = this.columnsArray.find((col) => col.isToday);
            if (column) {
                if (this.data.timer?.row) {
                    const newValue = this.data.timer.row.cells[column.id].value + value;
                    this.data.timer.row.updateCell(column, newValue, this.data);
                } else {
                    await this.reload(this.searchParams);
                }
            }
        }
        if (this.data.timer?.row) {
            this.data.timer.row.timerRunning = false;
        }
        delete this.data.timer;
    }

    async deleteTimer() {
        await this.timerService.deleteTimer();
        if (this.data.timer.row) {
            this.data.timer.row.timerRunning = false;
        }
        delete this.data.timer;
    }

    async addTime(data) {
        const timesheetId = this.data.timer && this.data.timer.id;
        await this.orm.call(this.resModel, "action_add_time_to_timesheet", [timesheetId, data]);
        await this.reload();
    }
}
