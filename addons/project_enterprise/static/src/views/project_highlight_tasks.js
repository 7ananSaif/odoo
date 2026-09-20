import { useService } from "@web/core/utils/hooks";

export function useProjectModelActions({ getContext }) {
    const orm = useService("orm");
    return {
        async getHighlightIds() {
            const context = getContext();
            if (!context || !context.highlight_conflicting_task) {
                return;
            }

            if (context.highlight_conflicting_task) {
                const highlightConflictingIds = await orm.search("project.task", [
                    ["planning_overlap", "!=", false],
                ]);
                return highlightConflictingIds;
            }
            return [];
        },
    };
}
