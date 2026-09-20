import { EventBus, reactive } from "@odoo/owl";

import { Domain } from "@web/core/domain";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { getFieldFromRegistry, getPropertyFieldInfo } from "@web/views/fields/field";

import { timerService } from "@timer/services/timer_service";

export const timesheetTimerService = {
    async: [
        ...timerService.async,
        "deleteTimer",
        "getRunningTimer",
        "startTimer",
        "stopTimer",
        "fetchTimerHeaderFields",
    ],
    dependencies: ["timer", "orm"],
    start(env, { timer: timerService, orm }) {
        let stepTimer = 0;
        let timesheetTimerFields;
        const timer = timerService.createTimer();
        const timerState = reactive({ isRunning: false });
        const bus = new EventBus();
        return {
            ...timerService,
            get timerState() {
                return timerState;
            },
            get stepTimer() {
                return stepTimer;
            },
            get otherCompany() {
                return timerState.data?.other_company ?? false;
            },
            get timesheetTimerFields() {
                return timesheetTimerFields;
            },
            set timesheetTimerFields(fields) {
                timesheetTimerFields = fields;
            },
            get bus() {
                return bus;
            },
            getTimesheetTimerFieldInfo(fieldName, fields = {}) {
                const field = fields[fieldName] || timesheetTimerFields[fieldName];
                if (!field) {
                    return {};
                }
                const propertyField = {
                    ...field,
                    domain: field.domain || "[]",
                    required: "False",
                };
                const fieldInfo = getPropertyFieldInfo(propertyField);
                if (fieldName === "task_id") {
                    fieldInfo.field = getFieldFromRegistry(propertyField.type, "task_with_hours");
                }
                fieldInfo.placeholder = field.string || "";
                if (fieldName === "project_id") {
                    fieldInfo.domain = Domain.and([
                        fieldInfo.domain,
                        new Domain([["allow_timesheets", "=", true]]),
                    ]).toString();
                    fieldInfo.context = `{'search_default_my_projects': True}`;
                    fieldInfo.required = "True";
                } else if (fieldName === "task_id") {
                    fieldInfo.context = `{'default_project_id': project_id, 'search_default_my_tasks': True, 'search_default_open_tasks': True, 'hide_timesheet_ids': true}`;
                } else if (fieldName === "name") {
                    fieldInfo.placeholder = _t("Describe your activity...");
                }
                if (field.depends?.length) {
                    fieldInfo.onChange = true;
                }
                return fieldInfo;
            },
            updateTimer(timerData = null) {
                timerState.data = timerData;
                timerState.isRunning = Boolean(timerData);
            },
            async deleteTimer() {
                if (timerState.data.id) {
                    await orm.call("account.analytic.line", "action_timer_unlink", [
                        timerState.data.id,
                    ]);
                }
                timer.resetTimer();
                timerState.data = null;
                timerState.isRunning = false;
            },
            async getRunningTimer() {
                if (!timerState.data) {
                    const { step_timer, ...data } = await orm.call(
                        "account.analytic.line",
                        "get_running_timer"
                    );
                    stepTimer = step_timer;
                    timerState.data = data;
                    if (timerState.data.id) {
                        timerState.isRunning = true;
                    }
                }
                return timerState.data;
            },
            async startTimer(vals = {}, notifyTimerChanged = false) {
                if (vals.id) {
                    timerState.data = await orm.call(
                        "account.analytic.line",
                        "action_timer_start",
                        [vals.id]
                    );
                } else {
                    const result = await orm.call(
                        "account.analytic.line",
                        "action_start_new_timesheet_timer",
                        [vals]
                    );
                    const { step_timer, ...data } = result;
                    stepTimer = step_timer;
                    timerState.data = data;
                }
                timerState.isRunning = true;
                if (notifyTimerChanged) {
                    bus.trigger("start_timer");
                }
                return timerState.data;
            },
            async stopTimer(args = [], kwargs = {}, notifyTimerChanged = false) {
                if (!timerState.isRunning) {
                    return 0;
                }
                const result = await orm.call(
                    "account.analytic.line",
                    "action_timer_stop",
                    [timerState.data.id, ...args],
                    kwargs
                );
                timer.resetTimer();
                timerState.isRunning = false;
                timerState.data = null;
                if (notifyTimerChanged) {
                    bus.trigger("stop_timer");
                }
                return result;
            },
            async fetchTimerHeaderFields(fieldNames) {
                timesheetTimerFields = await orm.call("account.analytic.line", "fields_get", [
                    fieldNames,
                ]);
                return timesheetTimerFields;
            },
            async updateTimerState(timesheet) {
                timerState.data = Object.fromEntries(
                    Object.entries(timerState.data).map(([fName, value]) => {
                        if (!(fName in timesheet._values)) {
                            return [fName, value];
                        }
                        const fieldType = timesheet.fields[fName].type;
                        const valueFormatted =
                            fieldType === "many2one"
                                ? timesheet._formatServerValue(fieldType, value)
                                : value;
                        let newValue = timesheet.data[fName];
                        const newValueFormatted = timesheet._formatServerValue(fieldType, newValue);
                        if (fieldType !== "many2one") {
                            newValue = newValueFormatted;
                        }
                        return [fName, valueFormatted !== newValueFormatted ? newValue : value];
                    })
                );
                if (timesheet.resId && !timerState.data.id) {
                    timerState.data.id = timesheet.resId;
                }
            },
        };
    },
};

registry.category("services").add("timesheet_timer", timesheetTimerService);
