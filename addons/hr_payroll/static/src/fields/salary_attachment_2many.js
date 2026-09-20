import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class SalaryAttachment2ManyField extends X2ManyField {
    /**
     * @override
     */
    setup() {
        super.setup();
        this.orm = useService("orm");
    }

    /**
     * @override
     */
    async openRecord(record) {
        if (this.canOpenRecord) {
            const action = await this.orm.call(
                "hr.salary.attachment",
                "action_open_employee_salary_attachment",
                [[record.resId]]
            );
            await this.action.doAction(
                {
                    ...action,
                    context: this.props.context,
                },
                {
                    onClose: () => this.props.record.load(),
                }
            );
        }
    }

    /**
     * @override
     */
    get rendererProps() {
        const props = super.rendererProps;
        props.activeActions.onDelete = this.onDelete.bind(this);
        return props;
    }

    async onDelete(record) {
        await this.orm.call("hr.salary.attachment", "action_unlink", [[record.resId]], {
            context: this.props.context,
        });
        this.props.record.load();
    }
}

export const salaryAttachment2ManyField = {
    ...x2ManyField,
    component: SalaryAttachment2ManyField,
};

registry.category("fields").add("salary_attachment_2many", salaryAttachment2ManyField);
