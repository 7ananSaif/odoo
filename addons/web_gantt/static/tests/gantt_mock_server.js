import { makeKwArgs, onRpc } from "@web/../tests/web_test_helpers";

onRpc("get_gantt_data", function getGanttData({ kwargs, model }) {
    let groups = this.env[model].formatted_read_group({
        ...kwargs,
        aggregates: ["id:array_agg"],
        limit: null,
        offset: 0,
    });

    const length = groups.length;
    const offset = kwargs.offset || 0;
    groups = groups.slice(offset, kwargs.limit ? kwargs.limit + offset : undefined);

    const recordIds = [];
    for (const group of groups) {
        group.__record_ids = group["id:array_agg"];
        delete group["id:array_agg"];
        recordIds.push(...(group.__record_ids || []));
    }

    const { records } = this.env[model].web_search_read(
        [["id", "in", recordIds]],
        kwargs.read_specification,
        makeKwArgs({ context: kwargs.context })
    );

    const unavailabilities = {};
    for (const fieldName of kwargs.unavailability_fields || []) {
        unavailabilities[fieldName] = {};
    }

    const progress_bars = {};
    for (const fieldName of kwargs.progress_bar_fields || []) {
        progress_bars[fieldName] = {};
    }

    return {
        groups,
        length,
        records,
        unavailabilities,
        progress_bars,
    };
});
