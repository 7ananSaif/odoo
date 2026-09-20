import { onWillStart } from "@odoo/owl";

import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

import { TimesheetLeaderboard } from "@sale_timesheet_enterprise/components/timesheet_leaderboard/timesheet_leaderboard";

export function patchRenderer(Renderer) {
    patch(Renderer.components, { TimesheetLeaderboard });
    patch(Renderer.prototype, {
        setup() {
            super.setup();
            this.timesheetLeaderboardService = useService("timesheet_leaderboard");
            onWillStart(async () => {
                await this.timesheetLeaderboardService.getLeaderboardData();
            });
        },
    });
}
