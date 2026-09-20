import { registry } from "@web/core/registry";

function _mockGetGanttData(params) {
    let groups = this._mockFormattedReadGroup({ ...params, aggregates: ["id:array_agg"] });
    if (params.limit) {
        // we don't care about pager feature in sample mode
        // but we want to present something coherent
        groups = groups.slice(0, params.limit);
    }
    const length = groups.length;
    groups.forEach((g) => (g["id:array_agg"] = g.id)); // the sample server does not use the key id:array_agg

    const unavailabilities = {};
    for (const fieldName of params.unavailability_fields || []) {
        unavailabilities[fieldName] = {};
    }

    const progress_bars = {};
    for (const fieldName of params.progress_bar_fields || []) {
        progress_bars[fieldName] = {};
    }

    return { groups, length, records: [], unavailabilities, progress_bars };
}

registry.category("sample_server").add("get_gantt_data", _mockGetGanttData);
