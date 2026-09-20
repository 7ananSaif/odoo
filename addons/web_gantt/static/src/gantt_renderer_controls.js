import { Component, useState } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { formatDate } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { pick } from "@web/core/utils/objects";
import { debounce } from "@web/core/utils/timing";
import { diffColumn } from "./gantt_helpers";
import { GanttScaleSelector } from "./gantt_scale_selector";

const { DateTime } = luxon;

const KEYS = ["startDate", "stopDate", "rangeId", "focusDate", "rescheduleMethod"];

export class GanttRendererControls extends Component {
    static template = "web_gantt.GanttRendererControls";
    static components = {
        Dropdown,
        DropdownItem,
        GanttScaleSelector,
    };
    static props = [
        "model",
        "displayExpandCollapseButtons",
        "focusToday",
        "getCurrentFocusDate",
        "slots?",
    ];
    static toolbarContentTemplate = "web_gantt.GanttRendererControls.ToolbarContent";
    static rangeMenuTemplate = "web_gantt.GanttRendererControls.RangeMenu";

    setup() {
        this.model = this.props.model;
        this.updateMetaData = debounce(() => this.model.fetchData(this.makeParams()), 500);
        this.state = useState(pick(this.model.metaData, ...KEYS));
    }

    getGanttScaleSelectorProps() {
        return {
            scales: {
                ...this.model.metaData.ranges,
                custom: {
                    description: _t("From: %(from_date)s to: %(to_date)s", {
                        from_date: formatDate(this.state.startDate),
                        to_date: formatDate(this.state.stopDate),
                    }),
                },
            },
            currentScale: this.state.rangeId,
            setScale: this.selectRangeId.bind(this),
            selectCustomRange: this.selectCustomRange.bind(this),
            startDate: this.state.startDate,
            stopDate: this.state.stopDate,
        };
    }

    makeParams() {
        const params = pick(this.state, ...KEYS);
        if (this.state.keepCurrentFocusDate) {
            params.currentFocusDate = this.props.getCurrentFocusDate();
        }
        return params;
    }

    onTodayClicked() {
        const success = this.props.focusToday();
        if (success) {
            return;
        }
        this.state.focusDate = DateTime.local().startOf("day");
        if (this.state.rangeId === "custom") {
            const diff = diffColumn(this.state.startDate, this.state.stopDate, "day");
            if (diff === 0) {
                this.state.startDate = this.state.stopDate = this.state.focusDate;
            } else {
                const n = Math.floor(diff / 2);
                const m = diff - n;
                this.state.startDate = this.state.focusDate.minus({ day: n });
                this.state.stopDate = this.state.focusDate.plus({ day: m - 1 });
            }
        } else {
            Object.assign(
                this.state,
                this.model.getRangeFromDate(this.state.rangeId, this.state.focusDate)
            );
        }
        delete this.state.keepCurrentFocusDate;
        this.updateMetaData();
    }

    selectRange(direction) {
        const sign = direction === "next" ? 1 : -1;
        const { focusDate, rangeId, startDate, stopDate } = this.state;
        if (rangeId === "custom") {
            const diff = diffColumn(startDate, stopDate, "day") + 1;
            this.state.focusDate = focusDate.plus({ day: sign * diff });
            this.state.startDate = startDate.plus({ day: sign * diff });
            this.state.stopDate = stopDate.plus({ day: sign * diff });
        } else {
            Object.assign(
                this.state,
                this.model.getRangeFromDate(rangeId, focusDate.plus({ [rangeId]: sign }))
            );
        }
        delete this.state.keepCurrentFocusDate;
        this.updateMetaData();
    }

    selectRangeId(rangeId) {
        Object.assign(
            this.state,
            this.model.getRangeFromDate(rangeId, DateTime.now().startOf("day"))
        );
        delete this.state.keepCurrentFocusDate;
        this.updateMetaData();
    }

    selectCustomRange(startDate, stopdDate) {
        this.state.rangeId = "custom";
        this.state.startDate = startDate;
        this.state.stopDate = stopdDate;
        this.state.keepCurrentFocusDate = true;
        this.updateMetaData();
    }

    get displayRescheduleMethods() {
        return (
            this.model.metaData.dependencyEnabled && !this.model.useSampleModel && !this.env.isSmall
        );
    }

    selectRescheduleMethod(method) {
        Object.assign(this.state, { rescheduleMethod: method });
        this.updateMetaData();
    }
}
