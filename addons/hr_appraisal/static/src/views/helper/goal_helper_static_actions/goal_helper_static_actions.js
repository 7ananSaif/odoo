import { _t } from "@web/core/l10n/translation";

export function useGoalStaticAction(model) {
    const records = model.root.selection;
    return {
        save_as_template: {
            isAvailable: () => records.every((r) => !r.data.template_goal_id),
            sequence: 50,
            description: _t("Save as template"),
            icon: "fa fa-save",
            callback: async () => {
                const action = await model.orm.call('hr.appraisal.goal', 'action_save_as_template', [records.map((r) => r.resId)]);
                return model.action.doAction(action);
            },
            groupNumber: 2,
        },
        mark_as_done: {
            isAvailable: () => records.every((r) => r.data.progression < 100),
            sequence: 60,
            description: _t("Mark as Done"),
            icon: "fa fa-check",
            callback: async () => {
                await model.orm.call('hr.appraisal.goal', 'action_confirm', records.map((r) => r.resId));
                await model.load();
            },
            groupNumber: 2,
        }
    };
}
