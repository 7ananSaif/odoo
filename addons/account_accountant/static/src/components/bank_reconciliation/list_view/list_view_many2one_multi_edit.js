import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { computeM2OProps, Many2One } from "@web/views/fields/many2one/many2one";
import { buildM2OFieldDescription, Many2OneField } from "@web/views/fields/many2one/many2one_field";

export class BankRecMany2OneMultiID extends Component {
    static template = "account_accountant.BankRecMany2OneMultiID";
    static components = { Many2One };
    static props = { ...Many2OneField.props };

    get m2oProps() {
        const props = computeM2OProps(this.props);
        if (this.props.record.selected && this.props.record.model.multiEdit) {
            props.context.active_ids = this.env.model.root.selection.map((r) => r.resId);
        }
        return props;
    }
}

registry.category("fields").add("bank_rec_list_many2one_multi_id", {
    ...buildM2OFieldDescription(BankRecMany2OneMultiID),
});
