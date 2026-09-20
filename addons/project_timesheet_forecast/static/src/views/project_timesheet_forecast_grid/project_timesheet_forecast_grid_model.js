import { Domain } from "@web/core/domain";
import { serializeDate } from "@web/core/l10n/dates";
import { patch } from "@web/core/utils/patch";
import { TimesheetGridModel } from "@timesheet_grid/views/timesheet_grid/timesheet_grid_model";

patch(TimesheetGridModel.prototype, {
    /**
     * @override
     */
    _postFetchAdditionalData(metaData) {
        const additionalGroups = super._postFetchAdditionalData(metaData);
        const { searchParams, sectionField, rowFields } = metaData;

        if (
            !searchParams.context.group_expand ||
            this.navigationInfo.periodEnd <= this.today
        ) {
            return additionalGroups;
        }

        /*
         * The goal of this code is to add records in the grid in order to ease encoding.
         * We will add entries if there are published 'slots' for the current employee, within a defined timeline
         * (depending on the scale).
         */

        const validPlanningFields = ["project_id", "employee_id"];
        const validRowFields = [];
        if (sectionField && validPlanningFields.includes(sectionField.name)) {
            validRowFields.push(sectionField.name);
        }
        for (const rowField of rowFields) {
            if (validPlanningFields.includes(rowField.name)) {
                validRowFields.push(rowField.name);
            }
        }

        if (!validRowFields.length) {
            return additionalGroups;
        }

        const domain = new Domain([
            ["employee_id", "!=", false],
            ["employee_id.user_id", "in", [false, searchParams.context.uid]],
            ["state", "=", "published"],
            ["project_id.allow_timesheets", "=", true],
            ["start_datetime", "<", serializeDate(this.navigationInfo.periodEnd)],
            ["end_datetime", ">", serializeDate(this.navigationInfo.periodStart)],
        ]);

        const fieldsToRemove = [];
        const searchDomain = new Domain(searchParams.domain);
        let additionalDomain = searchDomain;
        for (const tuple of searchDomain.ast.value) {
            if (
                tuple.type === 10
                && !['project_id', 'employee_id', 'user_id'].includes(tuple.value[0].value)
            ) {
                fieldsToRemove.push(tuple.value[0].value);
            }
        }
        if (fieldsToRemove.length) {
            additionalDomain = Domain.removeDomainLeaves(additionalDomain, fieldsToRemove);
        }
        const previousWeekSlotsInfo = this.orm.formattedReadGroup(
            "planning.slot",
            Domain.and([additionalDomain, domain]).toList({}),
            validRowFields,
            [],
        );

        /*
         * Convert timesheet info returned from 'project.project' and 'project.task' queries into the right data
         * formatting.
         */
        const prepareAdditionalData = (records, fieldName) => {
            const additionalData = {};
            for (const record of records) {
                let sectionKey = false;
                let sectionValue = null;
                if (sectionField) {
                    sectionKey = this._generateSectionKey(record, sectionField);
                    sectionValue = record[sectionField.name];
                }
                const rowKey = this._generateRowKey(record, metaData);
                const { domain, values } = this._generateRowDomainAndValues(record, rowFields);
                if (!(sectionKey in additionalData)) {
                    additionalData[sectionKey] = {
                        value: sectionValue,
                        rows: {},
                    };
                }
                if (!(rowKey in additionalData[sectionKey].rows)) {
                    additionalData[sectionKey].rows[rowKey] = {
                        domain: domain,
                        values,
                    };
                }
            }

            return additionalData;
        };

        additionalGroups.push(
            previousWeekSlotsInfo.then((groups) => {
                const timesheet_data = groups.map((r) => {
                    const d = {};
                    for (const validRowField of validRowFields) {
                        d[validRowField] = r[validRowField];
                    }
                    return d;
                });
                return prepareAdditionalData(timesheet_data);
            })
        );

        return additionalGroups;
    },
});
