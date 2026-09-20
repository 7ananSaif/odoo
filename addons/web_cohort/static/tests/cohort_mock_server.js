import { onRpc } from "@web/../tests/web_test_helpers";
import { Domain } from "@web/core/domain";
import { deserializeDate, parseDate } from "@web/core/l10n/dates";

onRpc("get_cohort_data", function getCohortData({ kwargs, model }) {
    const displayFormats = {
        day: "dd MM yyyy",
        week: "WW kkkk",
        month: "MMMM yyyy",
        quarter: "Qq yyyy",
        year: "y",
    };
    const rows = [];
    let totalValue = 0;
    let initialChurnValue = 0;
    const columnsAvg = {};
    const domain = kwargs.domain;
    const groups = this.env[model].formatted_read_group({
        ...kwargs,
        groupby: [kwargs.date_start + ":" + kwargs.interval],
        aggregates: ["__count"],
    });
    const totalCount = groups.length;
    for (const group of groups) {
        const cohortStartDate = deserializeDate(
            group[kwargs.date_start + ":" + kwargs.interval][0]
        );
        const group_domain = Domain.and([domain, group.__extra_domain]).toList();
        const records = this.env[model].search_read(group_domain);
        let value = 0;
        if (kwargs.measure === "__count") {
            value = records.length;
        } else {
            if (records.length) {
                value = records
                    .map((r) => r[kwargs.measure])
                    .reduce(function (a, b) {
                        return a + b;
                    });
            }
        }
        totalValue += value;
        let initialValue = value;

        const columns = [];
        let colStartDate = cohortStartDate;
        if (kwargs.timeline === "backward") {
            colStartDate = colStartDate.plus({ [`${kwargs.interval}s`]: -15 });
        }
        for (let column = 0; column <= 15; column++) {
            if (!columnsAvg[column]) {
                columnsAvg[column] = { percentage: 0, count: 0 };
            }
            if (column !== 0) {
                colStartDate = colStartDate.plus({ [`${kwargs.interval}s`]: 1 });
            }
            if (colStartDate > luxon.DateTime.local()) {
                columnsAvg[column]["percentage"] += 0;
                columnsAvg[column]["count"] += 0;
                columns.push({
                    value: "-",
                    churn_value: "-",
                    percentage: "",
                });
                continue;
            }

            const compareDate = colStartDate.toFormat(displayFormats[kwargs.interval]);
            let colRecords = records.filter(
                (record) =>
                    record[kwargs.date_stop] &&
                    parseDate(record[kwargs.date_stop], { format: "yyyy-MM-dd" }).toFormat(
                        displayFormats[kwargs.interval]
                    ) == compareDate
            );
            let colValue = 0;
            if (kwargs.measure === "__count") {
                colValue = colRecords.length;
            } else {
                if (colRecords.length) {
                    colValue = colRecords
                        .map((x) => x[kwargs.measure])
                        .reduce(function (a, b) {
                            return a + b;
                        });
                }
            }

            if (kwargs.timeline === "backward" && column === 0) {
                colRecords = records.filter(
                    (record) =>
                        record[kwargs.date_stop] &&
                        parseDate(record[kwargs.date_stop], { format: "yyyy-MM-dd" }) >=
                            colStartDate
                );
                if (kwargs.measure === "__count") {
                    initialValue = colRecords.length;
                } else {
                    if (colRecords.length) {
                        initialValue = colRecords
                            .map((x) => x[kwargs.measure])
                            .reduce((a, b) => a + b);
                    }
                }
                initialChurnValue = value - initialValue;
            }
            const previousValue = column === 0 ? initialValue : columns[column - 1]["value"];
            const remainingValue = previousValue - colValue;
            const previousChurnValue =
                column === 0 ? initialChurnValue : columns[column - 1]["churn_value"];
            const churnValue = colValue + previousChurnValue;
            let percentage = value ? parseFloat(remainingValue / value) : 0;
            if (kwargs.mode === "churn") {
                percentage = 1 - percentage;
            }
            percentage = Number((100 * percentage).toFixed(1));
            columnsAvg[column]["percentage"] += percentage;
            columnsAvg[column]["count"] += 1;
            columns.push({
                value: remainingValue,
                churn_value: churnValue,
                percentage: percentage,
                domain: [],
                period: compareDate,
            });
        }
        rows.push({
            date: cohortStartDate.toFormat(displayFormats[kwargs.interval]),
            value,
            domain: group_domain,
            columns: columns,
        });
    }

    return {
        rows,
        avg: {
            avg_value: totalCount ? totalValue / totalCount : 0,
            columns_avg: columnsAvg,
        },
    };
});
