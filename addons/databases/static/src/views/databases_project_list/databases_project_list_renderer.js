import { _t } from "@web/core/l10n/translation";
import { ProjectProjectListRenderer } from "@project/views/project_project_list/project_project_list_renderer";

export class DatabasesProjectListRenderer extends ProjectProjectListRenderer {
    getColumnClass(column) {
        const superColumnClass = super.getColumnClass(column) || "";
        if (column.widget === "selection" && column.name.startsWith("database_kpi_properties.")) {
            return `${superColumnClass || ""} text-center`;
        }
        return superColumnClass;
    }

    getFieldClass(column) {
        const superFieldClass = super.getFieldClass(column);
        if (column.widget === "selection" && column.name.startsWith("database_kpi_properties.")) {
            return `${superFieldClass || ""} text-center fs-5`;
        }
        return superFieldClass;
    }

    makeTooltip(column) {
        const tooltip = JSON.parse(super.makeTooltip(column));

        if (column.name.startsWith("database_kpi_properties.")) {
            const propertyName = column.name.substr(24);
            if (propertyName.startsWith("account_journal_type_")) {
                tooltip.field.label = _t("Draft entries in journal %(journal_name)s", { journal_name: tooltip.field.label });
            } else if (propertyName.startsWith("account_return_")) {
                tooltip.field.label = _t("Tax return %(return_name)s", { return_name: tooltip.field.label });
            } else if (propertyName.startsWith("mail_activity_type_")) {
                tooltip.field.label = _t("Planned activities of type %(return_name)s", { return_name: tooltip.field.label });
            }
        }

        return JSON.stringify(tooltip);
    }
}
