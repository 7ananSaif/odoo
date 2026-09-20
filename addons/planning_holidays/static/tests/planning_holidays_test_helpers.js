import { defineModels } from "@web/../tests/web_test_helpers";
import { planningModels } from "@planning/../tests/planning_mock_models";

export function definePlanningHolidaysModels() {
    return defineModels(planningHolidaysModels);
}

export const planningHolidaysModels = { ...planningModels };
