import { HrGanttRenderer } from "@hr_gantt/hr_gantt_renderer";
import { WorkEntriesMultiSelectionButtons } from "@hr_work_entry_enterprise/work_entries_multi_selection_buttons";
import { onWillStart } from "@odoo/owl";
import { Domain } from "@web/core/domain";
import { serializeDate } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { formatFloatTime } from "@web/views/fields/formatters";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { WorkEntriesGanttPopover } from "./work_entries_gantt_popover";
import { WorkEntriesGanttRowProgressBar } from "./work_entries_gantt_row_progress_bar";

export class WorkEntriesGanttRenderer extends HrGanttRenderer {
    static pillTemplate = "hr_work_entry_enterprise.WorkEntriesGanttRenderer.Pill";
    static components = {
        ...HrGanttRenderer.components,
        Popover: WorkEntriesGanttPopover,
        GanttRowProgressBar: WorkEntriesGanttRowProgressBar,
        MultiSelectionButtons: WorkEntriesMultiSelectionButtons,
    };

    setup() {
        super.setup();
        onWillStart(async () => {
            const { globalStart, globalStop } = this.model.metaData;
            const contracts = await this.orm.formattedReadGroup(
                "hr.version",
                Domain.and([
                    [["contract_date_start", "<", serializeDate(globalStop)]],
                    Domain.or([
                        [["contract_date_end", ">", serializeDate(globalStart)]],
                        [["contract_date_end", "=", false]],
                    ]),
                ]).toList(),
                ["employee_id", "contract_date_start:day", "contract_date_end:day"],
                []
            );
            this.contractsByEmployee = new Map();
            for (const contract of contracts) {
                const employeeId = contract.employee_id[0];
                if (!this.contractsByEmployee.has(employeeId)) {
                    this.contractsByEmployee.set(employeeId, []);
                }
                this.contractsByEmployee.get(employeeId).push(contract);
            }
        });
    }

    /**
     * @override
     */
    getRowTypeHeight(type) {
        return { t0: 24, t1: 35, t2: 25 }[type];
    }

    /**
     * @override
     */
    getDurationStr(duration) {
        return formatFloatTime(duration, {
            noLeadingZeroHour: true,
        }).replace(/(:00|:)/g, "h");
    }

    /**
     * @override
     */
    getDisplayName(pill) {
        const { computePillDisplayName, scale } = this.model.metaData;
        const { id: scaleId } = scale;
        const { record } = pill;
        if (!computePillDisplayName) {
            return record.display_name;
        }
        if (scaleId === "month") {
            return record.display_code || "";
        }
        if (scaleId === "week") {
            return record.work_entry_type_id.display_name || "";
        }
        return "";
    }

    /**
     * @override
     */
    addTo(pill, group) {
        if (!pill.duration[group.col]) {
            return false;
        }
        group.pills.push(pill);
        group.aggregateValue += pill.duration[group.col];
        return true;
    }

    /**
     * @override
     */
    enrichPill(pill) {
        const enrichedPill = super.enrichPill(pill);
        enrichedPill.subName = this.getDurationStr(pill.record.duration);
        enrichedPill.className += ` justify-content-center flex-column px-1`;
        enrichedPill.duration = {
            [this.getFirstGridCol(pill)]: pill.record.duration,
        };
        const progressBarForEmployee =
            this.model.data?.progressBars.employee_id[pill.record.employee_id.id];
        if (progressBarForEmployee) {
            const date = pill.record.date.toISODate();
            Object.assign(enrichedPill, {
                maxDayDuration: progressBarForEmployee.max_per_day[date],
                dayDuration: progressBarForEmployee.value_per_day[date],
            });
        }
        return enrichedPill;
    }

    /**
     * @override
     */
    getGroupPillDisplayName(pill) {
        return this.getDurationStr(pill.aggregateValue);
    }

    /**
     * @override
     */
    async getPopoverProps(pill) {
        const record = pill.record;
        const props = await super.getPopoverProps(...arguments);
        const { canEdit } = this.model.metaData;
        props.buttons = [
            ...props.buttons,
            ...(record.duration >= 1
                ? [
                      {
                          id: "action_split",
                          text: _t("Split"),
                          class: "btn btn-sm btn-secondary",
                          onClick: () => {
                              this.model.mutex.exec(async () => {
                                  this.dialogService.add(
                                      FormViewDialog,
                                      {
                                          title: _t("Split Work Entry"),
                                          resModel: "hr.work.entry",
                                          onRecordSave: async (record) => {
                                              await this.orm.call("hr.work.entry", "action_split", [
                                                  props.resId,
                                                  {
                                                      duration: record.data.duration,
                                                      work_entry_type_id:
                                                          record.data.work_entry_type_id.id,
                                                      name: record.data.name,
                                                  },
                                              ]);
                                              return true;
                                          },
                                          context: {
                                              form_view_ref:
                                                  "hr_work_entry.hr_work_entry_calendar_gantt_view_form",
                                              default_duration: props.context.duration / 2,
                                              default_name: props.context.name,
                                              default_work_entry_type_id:
                                                  props.context.work_entry_type_id,
                                              default_employee_id: props.context.employee_id,
                                              default_date: props.context.date,
                                          },
                                          canExpand: false,
                                      },
                                      {
                                          onClose: () => {
                                              this.model.fetchData();
                                          },
                                      }
                                  );
                              });
                          },
                      },
                  ]
                : []),
            ...(canEdit
                ? [
                      {
                          id: "unlink",
                          text: _t("Delete"),
                          class: "btn btn-sm ms-auto btn-danger",
                          onClick: () => {
                              this.model.mutex.exec(async () => {
                                  await this.orm.unlink("hr.work.entry", [props.resId]);
                                  this.model.fetchData();
                              });
                          },
                      },
                  ]
                : []),
        ];
        return {
            ...props,
            title: record.work_entry_type_id.display_name + " - " + this.getDurationStr(record.duration),
            buttons: record.state === "validated" ? null : props.buttons,
        };
    }

    /**
     * @override
     */
    getPill(record) {
        const pill = super.getPill(record);
        const isLocked = record.state === "validated";
        return {
            ...pill,
            disableDrag: isLocked || pill.disableDrag,
            disableStartResize: true,
            disableStopResize: true,
        };
    }

    getSelectedRecords(selectedCells, predicate) {
        const records = new Set();
        for (const selectedCell of selectedCells) {
            const recordsInSelectedCell = this.mappingCellToRecords[selectedCell];
            for (const record of recordsInSelectedCell || []) {
                if (predicate(record)) {
                    records.add(record);
                }
            }
        }
        return [...records];
    }

    getCellsInfoInContract(cellsInfo) {
        return cellsInfo.filter((c) => {
            const { employee_id } = JSON.parse(c.rowId)[0];
            const start = serializeDate(c.start);
            const contracts = this.contractsByEmployee.get(employee_id[0]);
            return (contracts || []).some(
                (c) =>
                    c["contract_date_start:day"][0] <= start &&
                    (start <= c["contract_date_end:day"][0] || !c["contract_date_end:day"][0])
            );
        });
    }

    getCellsInfoWithoutValidatedWorkEntry(selectedCells) {
        const cellsWithoutValidatedWorkEntry = [];
        for (const selectedCell of selectedCells) {
            const recordsInSelectedCell = this.mappingCellToRecords[selectedCell];
            if ((recordsInSelectedCell || []).some((r) => r.state === "validated")) {
                continue;
            }
            cellsWithoutValidatedWorkEntry.push(selectedCell);
        }
        return this.getCellsInfo(cellsWithoutValidatedWorkEntry);
    }

    /**
     * @override
     */
    prepareMultiSelectionButtonsReactive() {
        const result = super.prepareMultiSelectionButtonsReactive();
        result.userFavoritesWorkEntries = this.model.userFavoritesWorkEntries || [];
        result.onQuickReplace = (values) => this.onMultiReplace(values, this.selectedCells);
        result.onQuickReset = () => this.onResetWorkEntries(this.selectedCells);
        return result;
    }

    /**
     * @override
     */
    updateMultiSelection() {
        super.updateMultiSelection(...arguments);
        this.multiSelectionButtonsReactive.userFavoritesWorkEntries = this.model.userFavoritesWorkEntries || [];
    }

    /**
     * @override
     */
    onMultiCreate(multiCreateData, selectedCells) {
        const cellsInfo = this.getCellsInfoInContract(this.getCellsInfo(selectedCells));
        return this.model.multiCreateRecords(multiCreateData, cellsInfo);
    }

    onMultiReplace(values, selectedCells) {
        const cellsInfo = this.getCellsInfoInContract(
            this.getCellsInfoWithoutValidatedWorkEntry(selectedCells)
        );
        const records = this.getSelectedRecords(selectedCells, (r) => r.state !== "validated");
        return this.model.multiReplaceRecords(values, cellsInfo, records);
    }

    onResetWorkEntries(selectedCells) {
        const cellsInfo = this.getCellsInfoWithoutValidatedWorkEntry(selectedCells);
        const recordIds = this.getSelectedRecordIds(selectedCells, (r) => r.state !== "validated");
        this.model.resetWorkEntries(cellsInfo, recordIds);
    }
}
