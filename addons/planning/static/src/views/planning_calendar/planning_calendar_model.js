import { user } from "@web/core/user";
import { CalendarModel } from "@web/views/calendar/calendar_model";
import { usePlanningModelActions } from "../planning_hooks";
import { planningAskRecurrenceUpdate} from "./planning_ask_recurrence_update/planning_ask_recurrence_update_hook";
import { _t } from "@web/core/l10n/translation";

export class PlanningCalendarModel extends CalendarModel {
    static services = [...CalendarModel.services, "dialog", "orm"];

    setup(params, services) {
        super.setup(...arguments);
        this.dialog = services.dialog;
        this.getHighlightIds = usePlanningModelActions({
            getHighlightPlannedIds: () => this.env.searchModel.highlightPlannedIds,
            getContext: () => this.env.searchModel._context,
        }).getHighlightIds;
        this.meta.scale = this.env.isSmall? "day" : this.meta.scale;
        this.isManager = null;
    }

    async load() {
        let groupProm;
        if (this.isManager === null) {
            groupProm = user.hasGroup("planning.group_planning_manager").then(result => this.isManager = result);
        }
        return Promise.all([super.load(...arguments), groupProm]);
    }

    get hasMultiCreate() {
        return super.hasMultiCreate && this.isManager;
    }

    get showMultiCreateTimeRange() {
         return false;
     }

    get defaultFilterLabel() {
        return _t("Open Shifts");
    }

    /**
     * @override
     */
    addFilterFields(record, filterInfo) {
        // For 'Resource' filters we need the resource_color for the colorIndex, for 'Role' filters we need the colorIndex
        if (filterInfo.fieldName == 'resource_id') {
            return {
                colorIndex: record.rawRecord.resource_type == 'material' ? record.rawRecord['resource_color'] : '',
                resourceType: record.rawRecord['resource_type'],
            };
        }
        return {
            ...super.addFilterFields(record, filterInfo),
            resourceType: record.rawRecord['resource_type'],
        };
    }

    /**
     * @override
     */
    async loadRecords(data) {
        this.highlightIds = await this.getHighlightIds();
        return await super.loadRecords(data);
    }

    /**
     * @override
     */
    async updateRecord(record) {
        const rec = this.records[record.id];
        if (rec.rawRecord.repeat) {
            const recurrenceUpdate = await planningAskRecurrenceUpdate(this.dialog);
            if (!recurrenceUpdate) {
                return this.notify();
            }
            record.recurrenceUpdate = recurrenceUpdate;
        }
        return await super.updateRecord(...arguments);
    }

    /**
     * @override
     */
    buildRawRecord(partialRecord, options = {}) {
        if (options.batch_create_calendar) {
            let days_to_hours = 0;
            if (options.schedule[0]['duration_days'] > 1){
                days_to_hours = (options.schedule[0]['duration_days'] - 1) * 24;
            }
            partialRecord.end = partialRecord.start.plus({hour: options.schedule[0]['end_time'] + days_to_hours});
            partialRecord.start = partialRecord.start.plus({hour: options.schedule[0]['start_time']});
        }
        const result = super.buildRawRecord(partialRecord, options);
        if (partialRecord.recurrenceUpdate) {
            result.recurrence_update = partialRecord.recurrenceUpdate;
        }
        return result;
    }

    /**
     * @override
     */
    makeFilterDynamic(filterInfo, previousFilter, fieldName, rawFilter, rawColors) {
        return {
            ...super.makeFilterDynamic(filterInfo, previousFilter, fieldName, rawFilter, rawColors),
            resourceType: rawFilter['resourceType'],
            colorIndex: rawFilter['colorIndex'],
        };
    }

    /**
     * @override
     */
    makeContextDefaults(rawRecord) {
        const context = super.makeContextDefaults(...arguments);
        if (["day", "week"].includes(this.meta.scale)) {
            context['planning_keep_default_datetime'] = true;
        }
        return context;
    }

    /**
     * @override
     */
    getAllDayDates(start, end) {
        return [start.startOf('day'), end.endOf('day')];
    }

    /**
     * @override
     */
    async multiCreateRecords(multiCreateData, dates) {
        if (!dates.length) {
            await this.load();
            return [];
        }
        const values = await multiCreateData.record.getChanges();
        if (values.template_id) {
            const schedule = await this.orm.read("planning.slot.template", [values['template_id']], ["start_time", "end_time", "duration_days"]);
            const records = [];
            const [section] = this.filterSections;
            for (const date of dates) {
                const rawRecord = this.buildRawRecord({ start: date }, {'batch_create_calendar': true, 'schedule': schedule});
                for (const filter of section.filters) {
                    if (filter.active && filter.type === "record") {
                        records.push({
                            ...rawRecord,
                            ...values,
                            [section.fieldName]: filter.value,
                        });
                    }
                }
            }
            if (records.length) {
                const createdRecords = await this.orm.call(this.meta.resModel, "create_batch_from_calendar", [[], records]);
                await this.load();
                return createdRecords
            }
            return [];
        }
    }

    /**
    * @override
    */
    fetchFilters(resModel, fieldNames) {
        return this.orm.call(resModel, "get_calendar_filters", [[], user.userId, fieldNames]);
    }

    /**
     * @override
     */
    makeFilterRecord(filterInfo, previousFilter, rawRecord) {
        let filterRecord = super.makeFilterRecord(...arguments);
        if (!filterRecord.value) {
            filterRecord.canRemove = false;
            filterRecord.label = _t("Open Shifts");
        }
        // We need the resource type to display the correct icon in the filter section in the side panel
        filterRecord.resourceType = rawRecord.resource_type;
        return filterRecord;
    }

    /*
    * @override
    */
    async loadFilters(data) {
        const loadedFilters = await super.loadFilters(data);
        if (!Object.keys(this.data.filterSections).length && loadedFilters.sections.resource_id?.filters) {
            // This is the first load of the view, we set the 'open shifts' filter to active
            loadedFilters.sections.resource_id.filters[0].active = true;
        }
        return loadedFilters;
    }
}
