import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { animationFrame, mockDate } from "@odoo/hoot-mock";
import { findComponent, makeMockServer, mountView } from "@web/../tests/web_test_helpers";
import { defineHrWorkEntryModels } from "@hr_work_entry/../tests/hr_work_entry_test_helpers";
import { WorkEntriesGanttController } from "@hr_work_entry_enterprise/work_entries_gantt_controller";
const { DateTime } = luxon;

describe.current.tags("desktop");
defineHrWorkEntryModels();

beforeEach(() => {
    mockDate("2025-01-01 12:00:00", +0);
});

function getGanttController(view) {
    return findComponent(view, (c) => c instanceof WorkEntriesGanttController);
}

test("Test work entry gantt without work entry type", async () => {
    const { env } = await makeMockServer();
    env["hr.work.entry"].create([
        {
            name: "Test Work Entry 0",
            employee_id: 100,
            work_entry_type_id: false,
            date: "2025-01-01",
            create_date: "2025-01-01",
            duration: 120,
        },
    ]);
    const gantt = await mountView({
        type: "gantt",
        resModel: "hr.work.entry",
    });
    expect(".o_gantt_renderer").toBeDisplayed({
        message: "Gantt view should be displayed even with work entries with false work entry type",
    });
    const controller = getGanttController(gantt);
    const data = {
        name: "Test New Work Entry",
        employee_id: 100,
        work_entry_type_id: false,
        create_date: "2025-01-01",
    };
    const cellInfo = {
        rowId: JSON.stringify([{ employee_id: [100, "Richard"] }]),
        start: DateTime.fromISO("2025-01-02"),
        stop: DateTime.fromISO("2025-01-03"),
    };
    await controller.model.multiCreateRecords(
        {
            record: {
                getChanges: () => data,
            },
        },
        [cellInfo]
    );
    await animationFrame();
    expect(".o_gantt_pill").toHaveCount(2, {
        message: "2 work entries should be displayed in the gantt view",
    });
});
