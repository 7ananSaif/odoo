import { projectModels } from "@project/../tests/project_models";
import { fields } from "@web/../tests/web_test_helpers";

export class ProjectTask extends projectModels.ProjectTask {
    planning_overlap = fields.Html();
    planned_date_start = fields.Date({ string: "Date Start" });
    allow_task_dependencies = fields.Boolean({ string: "Allow Task Dependencies", default: true });
    display_warning_dependency_in_gantt = fields.Boolean({
        string: "Display warning dependency in Gantt",
        default: true,
    });
    is_closed = fields.Boolean();

    get_all_deadlines() {
        return {
            milestone_id: [],
            project_id: this.env["project.project"].search_read(),
        };
    }
}

class ProjectMilestone extends projectModels.ProjectMilestone {
    deadline = fields.Date();
    is_deadline_exceeded = fields.Boolean({ string: "Is Deadline Exceeded" });
    is_reached = fields.Boolean({ string: "Is Reached" });
    project_id = fields.Many2one({ string: "Project", relation: "project.project" });

    _records = [
        {
            id: 1,
            name: "Milestone 1",
            deadline: "2021-06-01",
            project_id: 1,
            is_reached: true,
        },
        {
            id: 2,
            name: "Milestone 2",
            deadline: "2021-06-12",
            project_id: 1,
            is_deadline_exceeded: true,
        },
        { id: 3, name: "Milestone 3", deadline: "2021-06-24", project_id: 1 },
    ];
}

projectModels.ProjectTask = ProjectTask;
projectModels.ProjectMilestone = ProjectMilestone;
