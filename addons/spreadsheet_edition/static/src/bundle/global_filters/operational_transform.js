import * as spreadsheet from "@odoo/o-spreadsheet";
const { otRegistry } = spreadsheet.registries;
const { transformRangeData } = spreadsheet.helpers;

otRegistry.addTransformation(
    "REMOVE_GLOBAL_FILTER",
    ["EDIT_GLOBAL_FILTER"],
    (toTransform, executed) => (toTransform.filter.id === executed.id ? undefined : toTransform)
);

otRegistry.addTransformation(
    "REMOVE_COLUMNS_ROWS",
    ["EDIT_GLOBAL_FILTER", "ADD_GLOBAL_FILTER"],
    transformTextFilterRange
);
otRegistry.addTransformation(
    "ADD_COLUMNS_ROWS",
    ["EDIT_GLOBAL_FILTER", "ADD_GLOBAL_FILTER"],
    transformTextFilterRange
);

function transformTextFilterRange(toTransform, executed) {
    const filter = toTransform.filter;
    if (filter.type === "text" && filter.rangesOfAllowedValues) {
        const transformedRanges = filter.rangesOfAllowedValues
            .map((rangeData) => transformRangeData(rangeData, executed))
            .filter(Boolean);
        return {
            ...toTransform,
            filter: {
                ...filter,
                rangesOfAllowedValues: transformedRanges?.length ? transformedRanges : undefined,
            },
        };
    }
    return toTransform;
}
