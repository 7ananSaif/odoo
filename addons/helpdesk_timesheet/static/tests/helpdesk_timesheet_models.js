import { fields, defineModels } from "@web/../tests/web_test_helpers";
import { hrTimesheetModels } from "@hr_timesheet/../tests/hr_timesheet_models";
import { defineTimesheetModels } from "@timesheet_grid/../tests/hr_timesheet_models";
import { helpdeskModels } from "@helpdesk/../tests/helpdesk_test_helpers";

export class HelpdeskTeam extends helpdeskModels.HelpdeskTeam {
    _name = "helpdesk.team";

    project_id = fields.Many2one({
        relation: "project.project",
    });
}

export class HelpdeskTicket extends helpdeskModels.HelpdeskTicket {
    _name = "helpdesk.ticket";

    project_id = fields.Many2one({
        relation: "project.project",
    });
}

export class HRTimesheet extends hrTimesheetModels.HRTimesheet {
    helpdesk_ticket_id = fields.Many2one({
        relation: "helpdesk.ticket",
    });
    has_helpdesk_team = fields.Boolean();
}

hrTimesheetModels.HRTimesheet = HRTimesheet;
helpdeskModels.HelpdeskTicket = HelpdeskTicket;
helpdeskModels.HelpdeskTeam = HelpdeskTeam;

export function defineHelpdeskTimesheetModels() {
    defineModels(helpdeskModels);
    defineTimesheetModels();
}
