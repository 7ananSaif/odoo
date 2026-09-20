import { registry } from "@web/core/registry";

function _mockGetGanttData(_, { model, kwargs }) {
    let groups = this._mockFormattedReadGroup(model, {
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
        recordIds.push(...(group["id:array_agg"] || []));
    }

    const { records } = this.mockWebSearchReadUnity(model, [], {
        domain: [["id", "in", recordIds]],
        context: kwargs.context,
        specification: kwargs.read_specification,
    });

    const unavailabilities = {};
    for (const fieldName of kwargs.unavailability_fields || []) {
        unavailabilities[fieldName] = {};
    }

    const progress_bars = {};
    for (const fieldName of kwargs.progress_bar_fields || []) {
        progress_bars[fieldName] = {};
    }

    return { groups, length, records, unavailabilities, progress_bars };
}

registry.category("mock_server").add("get_gantt_data", _mockGetGanttData);
