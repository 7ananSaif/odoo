import { Domain } from "@web/core/domain";
import { defineModels, fields, models } from "@web/../tests/web_test_helpers";
import { hrModels } from "@hr/../tests/hr_test_helpers";

export class PlanningSlot extends models.Model {
    _name = "planning.slot";

    name = fields.Char();
    start_datetime = fields.Datetime({ string: "Start Date Time" });
    end_datetime = fields.Datetime({ string: "End Date Time" });
    allocated_hours = fields.Float();
    allocated_percentage = fields.Float();
    role_id = fields.Many2one({ relation: "planning.role" });
    color = fields.Integer();
    repeat = fields.Boolean();
    recurrency_id = fields.Many2one({ relation: "planning.recurrency" });
    recurrence_update = fields.Selection({
        selection: [
            ["this", "This shift"],
            ["subsequent", "This and following shifts"],
            ["all", "All shifts"],
        ],
    });
    resource_id = fields.Many2one({ relation: "resource.resource" });
    state = fields.Selection({
        selection: [
            ["draft", "Draft"],
            ["published", "Published"],
        ],
    });
    department_id = fields.Many2one({ relation: "hr.department" });
    employee_id = fields.Many2one({ relation: "hr.employee" });
    role_ids = fields.One2many({ relation: "planning.role" });
    resource_type = fields.Selection({
        selection: [
            ["user", "Human"],
            ["material", "Material"],
        ],
    });
    user_id = fields.Many2one({ relation: "res.users" });
    conflicting_slot_ids = fields.Many2many({ relation: "planning.slot" });
    resource_roles = fields.Many2many({ relation: "resource.resource" });
    resource_color = fields.Integer({ related: 'resource_id.color' });

    template_id = fields.Many2one({ relation: "planning.slot.template" });

    _gantt_resource_employees_working_periods(groups, start_time, end_time) {
        const resourceIds = new Set();
        for (const group of groups) {
            const resId = group.resource_id ? group.resource_id[0] : false;
            if (resId) {
                resourceIds.add(resId)
            }
        }

        const employeeIds = new Set();
        const employee_id_to_ressource_id = {}
        const working_periods = {}
        for (const resource of this.env["resource.resource"].browse([...resourceIds])) {
            if (!resource.employee_id) {
                continue
            }
            const resource_id = resource.id
            const employee_id = resource.employee_id[0]
            employeeIds.add(employee_id)
            employee_id_to_ressource_id[employee_id] = resource_id
            working_periods[resource_id] = []
        }

        if (employeeIds.size) {
            const hr_contract_read_group = this.env["hr.version"].formatted_read_group(
                new Domain([
                    ["employee_id", "in", [...employeeIds]],
                ]).toList(),
                ["employee_id", "contract_date_start:day", "contract_date_end:day"],
                [],
                "",
                "",
                "",
            );
            hr_contract_read_group.forEach((contract) => {
                const employee_id = contract.employee_id[0];
                const resource_id = employee_id_to_ressource_id[employee_id];
                working_periods[resource_id].push({
                    start: contract["contract_date_start:day"][1],
                    end: contract["contract_date_end:day"][1],
                });
            });
            employeeIds
                .difference(new Set(hr_contract_read_group.map((a) => a.employee_id[0])))
                .forEach((employee_id) => {
                    const resource_id = employee_id_to_ressource_id[employee_id]
                    working_periods[resource_id].push({
                        start: start_time,
                        end: end_time,
                    });
                });
        }

        return working_periods;
    }
}

export class PlanningRecurrency extends models.Model {
    _name = "planning.recurrency";

    repeat_interval = fields.Integer();
}

export class PlanningSlotTemplate extends models.Model {
    _name = "planning.slot.template";

    start_time = fields.Float();
    end_time = fields.Float();
    duration_days = fields.Integer();

    _records = [
        { id: 1, start_time: 9, end_time: 17, duration_days: 2 },
    ];
}

class PlanningFilterResource extends models.Model {
    _name = "planning.filter.resource";

    resource_id = fields.Many2one({ relation: "resource.resource" });
    checked = fields.Boolean();
    resource_type = fields.Selection({
        selection: [
            ["user", "Human"],
            ["material", "Material"],
        ],
    });
}

export class ResourceResource extends models.ServerModel {
    _name = "resource.resource";

    resource_type = fields.Selection({
        selection: [
            ["user", "Human"],
            ["material", "Material"],
        ],
    });
}

export class PlanningRole extends models.ServerModel {
    _name = "planning.role";
}

export const planningModels = {
    ...hrModels,
    PlanningSlot,
    PlanningRecurrency,
    PlanningSlotTemplate,
    PlanningFilterResource,
    ResourceResource,
    PlanningRole,
};

export function definePlanningModels() {
    defineModels(planningModels);
}
