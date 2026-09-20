import { useState, useComponent, onWillStart, useExternalListener } from "@odoo/owl";

import { useBus, useService } from "@web/core/utils/hooks";

export function useTimesheetTimer(isListView = false) {
    const component = useComponent(); // list/kanban renderer
    const resModel = component.props.list.resModel;
    const timesheetTimerService = useService("timesheet_timer");
    timesheetTimerService.timesheetTimerFields = component.props.list.fields;
    const timesheetUOMService = useService("timesheet_uom");
    let isTimesheetTimerRecordInsideList = false;
    const timerState = useState(timesheetTimerService.timerState);

    const createTimesheetTimerRecord = async (timesheetTimerData) => {
        const list = component.props.list;
        if (component.props.editable && !list.isGrouped) {
            await list.leaveEditMode();
        }
        isTimesheetTimerRecordInsideList = false;
        const { activeFields, context, model, fields } = list;
        const timesheetTimerResId = timesheetTimerData.id;
        if (!timesheetTimerResId && list.addNewRecord) {
            timerState.timesheet = await list.addNewRecord(true);
            return timerState.timesheet;
        }
        let timesheet;
        if (list.isGrouped) {
            timesheet = new model.constructor.Record(
                model,
                {
                    context,
                    activeFields,
                    resModel,
                    fields,
                    resId: timesheetTimerResId || false,
                    resIds: timesheetTimerResId ? [timesheetTimerResId] : [],
                    isMonoRecord: true,
                    mode: "edit",
                },
                timesheetTimerData,
                { manuallyAdded: !timesheetTimerResId }
            );
        } else {
            // then we can add the new record inside the list view.
            timesheet = list._createRecordDatapoint(timesheetTimerData, "edit");
            list._addRecord(timesheet, 0);
        }
        await timesheet.load();
        timerState.timesheet = timesheet;
    };

    const processTimerData = async (timesheetTimerData) => {
        const timesheet = component.props.list.records.find(
            (record) => record.resId === timesheetTimerData.id
        );
        if (timesheet) {
            isTimesheetTimerRecordInsideList = true;
            timesheet._switchMode("edit");
            timerState.timesheet = timesheet;
        } else {
            await createTimesheetTimerRecord(timesheetTimerData);
        }
    };

    const getRunningTimer = async () => {
        const timesheetTimerData = await timesheetTimerService.getRunningTimer(resModel);
        if (timesheetTimerData.id) {
            await processTimerData(timesheetTimerData);
        }
        return timesheetTimerData;
    };

    const startTimer = async () => {
        const timesheetTimerData = await timesheetTimerService.startTimer();
        if (timesheetTimerData) {
            await createTimesheetTimerRecord(timesheetTimerData);
        }
        timesheetTimerService.bus.trigger("timer_ready");
        return timesheetTimerData;
    };
    const postProcessTimerStopped = async () => {
        delete timerState.timesheet;
        await component.props.list.load();
    };
    const stopTimer = async () => {
        await timerState.timesheet.save();
        const result = await timesheetTimerService.stopTimer([true]);
        if (result) {
            await postProcessTimerStopped();
        }
        return result;
    };
    const deleteTimer = async () => {
        await timesheetTimerService.deleteTimer();
        await postProcessTimerStopped();
    };

    const onTimesheetTimerHeaderClick = async () => {
        const timesheet = timerState.timesheet;
        if (timesheet && !timesheet.isInEdition) {
            if (isListView && isTimesheetTimerRecordInsideList) {
                await component.props.list.enterEditMode(timesheet);
            } else {
                timesheet._switchMode("edit");
            }
        }
    };

    const onKeydown = (ev) => {
        if (
            component.props.list.editedRecord ||
            ["input", "textarea"].includes(ev.target.tagName.toLowerCase())
        ) {
            return;
        }
        const { otherCompany, timerRunning } = timerState;
        switch (ev.key) {
            case "Enter":
                ev.preventDefault();
                if (!otherCompany) {
                    if (timerRunning) {
                        stopTimer();
                    } else {
                        startTimer();
                    }
                }
                break;
            case "Escape":
                if (!otherCompany && timerRunning) {
                    ev.preventDefault();
                    deleteTimer();
                }
                break;
            case "Shift":
                ev.preventDefault();
                timerState.addTimeMode = true;
                break;
        }
    };

    const onKeyup = (ev) => {
        if (ev.key === "Shift") {
            timerState.addTimeMode = false;
        }
    };

    onWillStart(async () => {
        await getRunningTimer();
    });
    useExternalListener(window, "keydown", onKeydown.bind(this));
    useExternalListener(window, "keyup", onKeyup.bind(this));
    useBus(timesheetTimerService.bus, "start_timer", async (ev) => {
        if (timerState.timesheet?.resId !== timerState.data.id) {
            await component.props.list.load();
        }
        processTimerData(timerState.data);
    });
    useBus(timesheetTimerService.bus, "stop_timer", postProcessTimerStopped);

    return {
        get timerState() {
            return timerState;
        },
        get timesheetTimerRecord() {
            return timerState.timesheet;
        },
        get showTimer() {
            return timesheetUOMService.timesheetWidget === "float_time";
        },
        timesheetTimerService,
        getRunningTimer,
        startTimer,
        stopTimer,
        deleteTimer,
        onTimesheetTimerHeaderClick,
    };
}
