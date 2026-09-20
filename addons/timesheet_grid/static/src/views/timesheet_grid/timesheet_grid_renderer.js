import { _t } from "@web/core/l10n/translation";
import { deserializeDate } from "@web/core/l10n/dates";
import { GridRenderer } from "@web_grid/views/grid_renderer";
import { onWillStart, markup } from "@odoo/owl";

export class TimesheetGridRenderer extends GridRenderer {
    static components = {
        ...GridRenderer.components,
    };

    setup() {
        super.setup();
        onWillStart(this.onWillStart);
    }

    async onWillStart() {
        await this._fetchLastValidatedTimesheetDate();
    }

    async onWillUpdateProps(nextProps) {
        if (this.lastValidationDatePerEmployee === undefined) {
            await this._fetchLastValidatedTimesheetDate(nextProps);
        }
    }

    getUnavailableClass(column, cellData = {}) {
        if (!this.props.model.unavailabilityDaysPerEmployeeId) {
            return "";
        }
        const unavailabilityClass = "o_grid_unavailable";
        let employee_id = false;
        if (cellData.section && this.props.model.sectionField?.name === "employee_id") {
            employee_id = cellData.section.value && cellData.section.value[0];
        } else if (cellData.row && "employee_id" in cellData.row.valuePerFieldName) {
            employee_id =
                cellData.row.valuePerFieldName.employee_id &&
                cellData.row.valuePerFieldName.employee_id[0];
        }
        const unavailabilityDays = this.props.model.unavailabilityDaysPerEmployeeId[employee_id];
        return unavailabilityDays && unavailabilityDays.includes(column.value)
            ? unavailabilityClass
            : "";
    }

    getFieldAdditionalProps(fieldName) {
        const props = super.getFieldAdditionalProps(fieldName);
        if (fieldName in this.props.model.workingHoursData) {
            props.workingHours = this.props.model.workingHoursData[fieldName];
        }
        return props;
    }

    async _fetchLastValidatedTimesheetDate(props = this.props) {
        if (!props.model.useSampleModel) {
            await this._getLastValidatedTimesheetDate(props);
        }
    }

    async _getLastValidatedTimesheetDate(props = this.props) {
        this.lastValidationDatePerEmployee = {};
        const { sectionField, rowFields, employeeField, data } = props.model;
        if (sectionField?.name === employeeField.name) {
            const employeeIds = props.model._getFieldValuesInSectionAndRows(
                employeeField,
                sectionField,
                rowFields,
                data
            );
            if (employeeIds.length) {
                const result = await props.model.orm.call(
                    "hr.employee",
                    "get_last_validated_timesheet_date",
                    [employeeIds],
                );
                for (const [employeeId, lastValidatedTimesheetDate] of Object.entries(result)) {
                    this.lastValidationDatePerEmployee[employeeId] =
                        lastValidatedTimesheetDate && deserializeDate(lastValidatedTimesheetDate);
                }
            }
        }
    }

    get displayAddLine() {
        const res = super.displayAddLine;
        if (!res || this.props.sectionField?.name !== "employee_id") {
            return res;
        }

        const employeeId = this.row.section.valuePerFieldName.employee_id[0];
        if (employeeId in this.lastValidationDatePerEmployee) {
            return !this.lastValidationDatePerEmployee[employeeId] || this.lastValidationDatePerEmployee[employeeId].startOf("day") < this.props.model.navigationInfo.periodEnd.startOf("day");
        }

        return res;
    }

    getCellColorClass(column, section) {
        const res = super.getCellColorClass(...arguments);
        const workingHours =
            this.props.model.data.workingHours.dailyPerEmployee?.[section?.valuePerFieldName?.employee_id?.[0]];
        if (!workingHours) {
            return res;
        }

        const value = workingHours[column.value];
        const cellValue = section?.cells?.[column.id]?.value;
        if (cellValue > value) {
            return "text-warning";
        } else if (cellValue < value) {
            return "text-danger";
        } else if (cellValue === value) {
            return "text-success";
        }

        return res;
    }

    isTextDanger(row, column) {
        const params = this.props.model.searchParams;
        return (
            !params.groupBy.length ||
            params.groupBy[0] === "employee_id"
        ) && (row.cells[column.id].value > 24);
    }

    getWorkingHours(section) {
        const employee_id = section?.valuePerFieldName?.employee_id?.[0];
        if (!employee_id) {
            return null;
        }
        return this.props.model.data.workingHours.dailyPerEmployee?.[employee_id];
    }

    getSectionDailyOvertime(cell, workingHours) {
        if (workingHours?.hasOwnProperty(cell.column.value)) {
            return cell.value - workingHours[cell.column.value];
        }
        return 0;
    }

    getSectionOvertime(section) {
        const workingHours = this.getWorkingHours(section);
        if (workingHours == null) {
            return null;
        }
        if (workingHours.full_time_required_hours) {
            let isToday = false;
            let hoursWorked = 0;
            const isTodayColumn = this.props.columns.some((column) => column.isToday);
            for (const cell of Object.values(section.cells)) {
                if (isTodayColumn) {
                    if (isToday && !cell.column.isToday) {
                        // we don't count after today
                        break;
                    } else if (!isToday && cell.column.isToday) {
                        isToday = true;
                    }
                }
                hoursWorked += cell.value;
            }
            return hoursWorked - workingHours.full_time_required_hours;
        }

        return Object.values(section.cells).reduce((overtime, cell) => overtime + this.getSectionDailyOvertime(cell, workingHours), 0);
    }

    _getTotalCellBgColor(section) {
        const weeklyOvertime = this.getSectionOvertime(section);
        const res = super._getTotalCellBgColor(section);
        if (weeklyOvertime == null) {
            return res;
        } else if (weeklyOvertime < 0) {
            return 'text-bg-danger';
        } else if (weeklyOvertime === 0) {
            return 'text-bg-success';
        } else {
            return 'text-bg-warning';
        }
    }

    getCellsTextClasses(column, row) {
        const res = super.getCellsTextClasses(...arguments);
        if (this.props.model.searchParams.groupBy[0] === "employee_id") {
            res[this.getCellColorClass(column, row)] = true;
        }
        return res;
    }

    getTotalCellsTextClasses(row, grandTotal) {
        const res = super.getTotalCellsTextClasses(...arguments);
        // Limit applying color when multi groupby of employees when the row is section
        if (this.props.model.searchParams.groupBy[0] === "employee_id" && row.section.isFake) {
            Object.assign(res, { [this._getTotalCellBgColor(row)]: true });
            delete res["text-bg-200"];
        }
        return res;
    }

    /** Return grid cell action helper when no records are found */
    _getNoContentHelper() {
        const noActivitiesFound = _t("No timesheets found. Let's create one!");
        const noContentTimesheetHelper = _t("Keep track of your working hours by project every day and bill your customers for that time.");
        return markup`<p class='o_view_nocontent_smiling_face'>${noActivitiesFound}</p><p>${noContentTimesheetHelper}</p>`;
    }
}
