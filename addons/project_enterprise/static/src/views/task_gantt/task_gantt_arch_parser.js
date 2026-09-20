import { TaskGanttArchParserCommon } from "@project_enterprise/views/project_task_common/task_gantt_arch_parser_common";

export class TaskGanttArchParser extends TaskGanttArchParserCommon {
    parse() {
        const archInfo = super.parse(...arguments);
        if (archInfo.dependencyEnabled) {
            archInfo.decorationFields.push('display_warning_dependency_in_gantt');
        }
        return archInfo;
    }
}
