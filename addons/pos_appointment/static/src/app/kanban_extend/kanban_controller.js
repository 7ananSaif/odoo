/* global posmodel */

import { localization } from "@web/core/l10n/localization";
import { useState, onMounted } from "@odoo/owl";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { DateTimePickerPopover } from "@web/core/datetime/datetime_picker_popover";
import { usePopover } from "@web/core/popover/popover_hook";
import { Domain } from "@web/core/domain";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { serializeDateTime } from "@web/core/l10n/dates";

const { DateTime } = luxon;

export class PosKanbanController extends KanbanController {
    static template = "pos_restaurant_appointment.KanbanController";
    static components = {
        ...KanbanController.components,
        Dropdown,
        DropdownItem,
    };

    setup() {
        super.setup(...arguments);
        this.popover = usePopover(DateTimePickerPopover, { position: "bottom" });
        this.state = useState({
            date: DateTime.now(),
            period: "",
        });
        this.model = this.env.model;
        this.localization = localization;
        this.searchModel = this.model.env.searchModel;
        this.timeRanges = {
            morning: { startHour: 0, endHour: 11 },
            lunch: { startHour: 11, endHour: 17 },
            evening: { startHour: 17, endHour: 24 },
        };
        onMounted(async () => {
            const kanbanDateFilter = Object.values(this.searchModel.searchItems).find(
                (sm) => sm.name === "kanban_date_filter"
            );
            if (!kanbanDateFilter?.id) {
                await this._applyFilter("date", this.state.date);
            } else {
                this.state.date = DateTime.fromFormat(
                    kanbanDateFilter.description.replace("Start is ", ""),
                    this.localization.dateFormat
                );
                this.searchModel.toggleSearchItem(kanbanDateFilter.id);
            }
            const kanbanHourFilter = Object.values(this.searchModel.searchItems).find(
                (sm) => sm.name === "kanban_hour_filter"
            );
            if (!kanbanHourFilter?.id) {
                const currentHour = DateTime.now().hour;
                if (currentHour < 11) {
                    this._applyFilter("hour", "morning");
                } else if (currentHour < 17) {
                    this._applyFilter("hour", "lunch");
                } else {
                    this._applyFilter("hour", "evening");
                }
            } else {
                this.state.period = kanbanHourFilter.description.replace("Hour is ", "");
                this.searchModel.toggleSearchItem(kanbanHourFilter.id);
            }
        });
    }

    async _applyFilter(filterType, value) {
        const searchModel = this.searchModel;
        let domain;
        let description;
        let name;
        if (filterType === "date") {
            name = "kanban_date_filter";
            description = `Start is ${value.toFormat(this.localization.dateFormat)}`;
            domain = Domain.and([
                new Domain([
                    [
                        "start",
                        ">=",
                        serializeDateTime(value.set({ hour: 0, minute: 0, second: 0 })),
                    ],
                ]),
                new Domain([
                    [
                        "start",
                        "<=",
                        serializeDateTime(value.set({ hour: 23, minute: 59, second: 59 })),
                    ],
                ]),
            ]);
        } else if (filterType === "hour") {
            this.state.period = value.charAt(0).toUpperCase() + value.slice(1);
            name = "kanban_hour_filter";
            description = `Hour is ${this.state.period}`;
            const date = this.state.date || DateTime.now();
            const { startHour, endHour } = this.timeRanges[value];
            const from = date.set({ hour: startHour, minute: 0, second: 0 });
            const to = date.set({ hour: endHour - 1, minute: 59, second: 59 });
            domain = new Domain([
                ["start", ">=", serializeDateTime(from)],
                ["start", "<=", serializeDateTime(to)],
            ]);
        } else {
            return;
        }
        const existingFilter = Object.values(searchModel.searchItems).find(
            (si) => si.name === name
        );
        if (existingFilter) {
            existingFilter.domain = domain.toString();
            existingFilter.description = description;
            searchModel._notify();
            if (!searchModel.query.some((q) => q.searchItemId === existingFilter.id)) {
                searchModel.toggleSearchItem(existingFilter.id);
            }
        } else {
            searchModel.createNewFilters([
                {
                    description: description,
                    domain: domain.toString(),
                    invisible: "True",
                    type: "filter",
                    name: name,
                },
            ]);
        }
    }

    onClickDateBtn(ev) {
        this.popover.open(ev.currentTarget, {
            pickerProps: {
                onSelect: async (value) => {
                    if (value) {
                        this.state.date = value;
                        await this._applyFilter("date", value);
                        const kanbanHourFilter = Object.values(this.searchModel.searchItems).find(
                            (sm) => sm.name === "kanban_hour_filter"
                        );
                        if (kanbanHourFilter && this.state.period) {
                            this.onClickHourFilter(
                                this.state.period.charAt(0).toLowerCase() +
                                    this.state.period.slice(1)
                            );
                        }
                    } else {
                        this.onRemove();
                    }
                    this.popover.close();
                },
                type: "date",
                value: this.state.date,
            },
        });
    }

    onRemove(ev, filterType) {
        ev.stopPropagation();
        var filterName = filterType === "date" ? "kanban_date_filter" : "kanban_hour_filter";
        const kanbanFilter = Object.values(this.searchModel.searchItems).find(
            (sm) => sm.name === filterName
        );
        if (
            kanbanFilter &&
            this.searchModel.query.some((sm) => sm.searchItemId === kanbanFilter.id)
        ) {
            this.searchModel.toggleSearchItem(kanbanFilter.id);
        }
        if (filterType === "date") {
            this.state.date = null;
        } else {
            this.state.period = "";
        }
    }

    get totalPersonCount() {
        return this.model.root.groups.reduce((groupSum, group) => {
            const groupTotal = group.list.records.reduce(
                (recordSum, record) => recordSum + record.data.waiting_list_capacity,
                0
            );
            return groupSum + groupTotal;
        }, 0);
    }

    async createRecord() {
        const action = await this.env.model.orm.call(
            "calendar.event",
            "action_create_booking_form_view",
            [false, posmodel.config.raw.appointment_type_id]
        );
        return this.env.model.action.doAction(action, {
            onClose: async () => {
                const root = this.env.model.root;
                const { limit, offset } = root;
                await root.load({ offset, limit });
            },
        });
    }

    onClickHourFilter(period) {
        this._applyFilter("hour", period);
    }
}
