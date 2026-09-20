import { serializeDate } from "@web/core/l10n/dates";
import { user } from "@web/core/user";
import { localStartOf } from "@web_gantt/gantt_helpers";
import { GanttModel } from "@web_gantt/gantt_model";

const { DateTime } = luxon;

export class WorkEntriesGanttModel extends GanttModel {
    _getGroupedBy() {
        return ["employee_id"];
    }

    getRange() {
        const { globalStart, globalStop } = this._buildMetaData();
        return { start: globalStart, end: globalStop.minus({ millisecond: 1 }) };
    }

    getRangeFromDate(rangeId, date) {
        const startDate = localStartOf(date, rangeId);
        const stopDate = startDate.plus({ [rangeId]: 1 }).minus({ day: 1 });
        return { focusDate: date, startDate, stopDate, rangeId };
    }

    async resetWorkEntries(cellsInfo, recordIds) {
        const cellsFormattedData = [];
        for (const { start, rowId } of cellsInfo) {
            const schedule = this.getSchedule({ start, rowId });
            cellsFormattedData.push({ date: schedule.date, employee_id: schedule.employee_id });
        }
        await this.orm.call("hr.work.entry.regeneration.wizard", "regenerate_work_entries", [
            [],
            cellsFormattedData,
            recordIds,
        ]);
        await this.fetchData();
    }

    async multiReplaceRecords(values, cellsInfo, records) {
        if (!cellsInfo.length) {
            return;
        }
        const new_records = [];
        const quickreplace = (values.duration < 0);
        const newly_generated_entries = [];
        for (const { start, stop, rowId } of cellsInfo) {
            const schedule = this.getSchedule({ start, stop, rowId });
            if (quickreplace) {
                const selected_cell_records = records.filter((r) => r.employee_id.id === schedule.employee_id && r.date.toISODate() === schedule.date);
                const existing_duration = selected_cell_records.reduce((acc, r) => acc + r.duration, 0);
                if (existing_duration > 0)
                    values.duration = existing_duration;
                else {
                    const generated_work_entry = await this.orm.call(
                        "hr.employee",
                        "generate_work_entries",
                        [schedule.employee_id, schedule.date, schedule.date, true]
                    );
                    if (generated_work_entry.length > 0)
                        newly_generated_entries.push(generated_work_entry[0]);
                    continue
                }
            }
            new_records.push({ ...schedule, ...values });
        }
        await this.orm.write("hr.work.entry", newly_generated_entries, {
            work_entry_type_id: values.work_entry_type_id
        });
        const created = await this.orm.create(this.metaData.resModel, new_records, {
            context: { ...this.searchParams.context, multi_create: true },
        });
        if (records.length && created) {
            await this.orm.unlink(this.metaData.resModel, records.map((r) => r.id));
        }
        await this.fetchData();
    }

    /**
     * @protected
     * @override
     */
    _getDomain(metaData) {
        return this.searchParams.domain;
    }

    /**
     * @protected
     * @override
     */
    async _fetchData(metaData, additionalContext) {
        if (!this.orm.isSample) {
            const { start, end } = this.getRange();
            await this.orm.call("hr.employee", "generate_work_entries", [
                [],
                serializeDate(start),
                serializeDate(end),
            ]);
        }
        additionalContext = {
            ...(additionalContext || {}),
            gantt_start_date: serializeDate(metaData.globalStart),
            gantt_stop_date: serializeDate(metaData.globalStop),
        };
        await Promise.all([
            super._fetchData(...arguments, additionalContext),
            this._fetchUserFavoritesWorkEntries(),
        ]);
    }

    async _fetchUserFavoritesWorkEntries() {
        const userFavoritesWorkEntriesIds = await this.orm.formattedReadGroup(
            "hr.work.entry",
            [
                ["create_uid", "=", user.userId],
                ["create_date", ">", serializeDate(DateTime.local().minus({ months: 3 }))],
            ],
            ["work_entry_type_id", "create_date:day"],
            [],
            {
                order: "create_date:day desc",
                limit: 6,
            }
        );
        if (userFavoritesWorkEntriesIds.length) {
            this.userFavoritesWorkEntries = await this.orm.read(
                "hr.work.entry.type",
                userFavoritesWorkEntriesIds.map((r) => r.work_entry_type_id?.[0]).filter(Boolean),
                ["display_name", "display_code", "color"]
            );
            this.userFavoritesWorkEntries = this.userFavoritesWorkEntries.sort((a, b) =>
                a.display_code
                    ? a.display_code.localeCompare(b.display_code)
                    : a.display_name.localeCompare(b.display_name)
            );
        } else {
            this.userFavoritesWorkEntries = [];
        }
    }
}
