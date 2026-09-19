import {
    SkillsListRenderer,
    SkillsX2ManyField,
    skillsX2ManyField,
} from "@hr_skills/fields/skills_one2many/skills_one2many";

import { registry } from "@web/core/registry";

export class AppraisalSkillsListRenderer extends SkillsListRenderer {
    static template = "hr_appraisal_skills.AppraisalSkillsListRenderer";
    static props = [...AppraisalSkillsListRenderer.props];

    get fields() {
        const fields = this.props.list.fields;

        Object.values(fields).forEach((k) => {
            if (k.sortable) {
                k.sortable = false;
            }
        });
        return fields;
    }
}

export class AppraisalSkillsX2ManyField extends SkillsX2ManyField {
    static components = {
        ...SkillsX2ManyField.components,
        ListRenderer: AppraisalSkillsListRenderer,
    };
}

export const appraisalSkillsX2ManyField = {
    ...skillsX2ManyField,
    component: AppraisalSkillsX2ManyField,
};

registry.category("fields").add("appraisal_skills_one2many", appraisalSkillsX2ManyField);
