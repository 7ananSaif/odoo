import { registry } from "@web/core/registry";
import { PercentPieField, percentPieField } from "@web/views/fields/percent_pie/percent_pie_field";

export class AppraisalPercentPieField extends PercentPieField {
    static template = "hr_appraisal.AppraisalPercentPieField";

    get quotient() {
        return this.props.record.data["number_of_completed_sibling_goals"];
    }

    get dividend() {
        return this.props.record.data["number_of_sibling_goals"];
    }

    get title() {
        return this.props.record.data["parent_id"].display_name;
    }

}

export const appraisalPercentPieField = {
    ...percentPieField,
    component: AppraisalPercentPieField,
    fieldDependencies: [
        { name: "number_of_sibling_goals", type: "integer" },
        { name: "number_of_completed_sibling_goals", type: "integer" },
        { name: "parent_id", type: "many2one" },
    ],
};

registry.category("fields").add("appraisal_percentpie", appraisalPercentPieField);
