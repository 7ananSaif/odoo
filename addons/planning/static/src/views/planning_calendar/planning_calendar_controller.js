import { serializeDateTime } from "@web/core/l10n/dates";
import { CalendarController } from "@web/views/calendar/calendar_controller";
import { usePlanningControllerActions } from "../planning_hooks";
import { _t } from "@web/core/l10n/translation";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import {
    PlanningCalendarSidePanel
} from "./planning_calendar_side_panel/planning_calendar_side_panel";

export class PlanningCalendarController extends CalendarController {
    static components = {
        ...CalendarController.components,
        CalendarSidePanel: PlanningCalendarSidePanel,
    };

    setup() {
        super.setup(...arguments);

        const getDomain = () => this.model.computeDomain(this.model.data);
        this.planningControllerActions = usePlanningControllerActions({
            getDomain,
            getStartDate: () => this.model.rangeStart,
            getStopDate: () => this.model.rangeEnd,
            getRecords: () => Object.values(this.model.records),
            getResModel: () => this.model.resModel,
            getAdditionalContext: () => ({
                default_start_datetime: serializeDateTime(this.model.rangeStart),
                default_end_datetime: serializeDateTime(this.model.rangeEnd),
                default_slot_ids: Object.values(this.model.records).map(rec => rec.id),
                scale: this.model.scale,
                active_domain: getDomain(),
            }),
            toggleHighlightPlannedFilter: (highlightPlannedIds) => this.env.searchModel.toggleHighlightPlannedFilter(highlightPlannedIds),
            reload: () => this.model.load(),
        });
    }

    get editRecordDefaultDisplayText() {
        return _t("New Shift");
    }

    /**
     * @override
     */
    async editRecord(record, context = {}) {
        const newContext = {
            ...context,
            is_record_created: !record.id,
            view_start_date: serializeDateTime(this.model.rangeStart),
            view_end_date: serializeDateTime(this.model.rangeEnd),
        };
        return new Promise((resolve) => {
            this.displayDialog(
                FormViewDialog,
                {
                    resModel: this.model.resModel,
                    resId: record.id || false,
                    context: newContext,
                    title: record.id ? _t("Open: %s", record.title) : _t("New Event"),
                    viewId: this.model.formViewId,
                },
                {
                    onClose: () => {
                        this.model.load();
                        resolve();
                    },
                }
            );
        });
    }
}
