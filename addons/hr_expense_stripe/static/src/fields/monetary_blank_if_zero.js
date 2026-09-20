import { registry } from "@web/core/registry";
import { MonetaryField, monetaryField } from "@web/views/fields/monetary/monetary_field";

export class MonetaryFieldBlankIfZero extends MonetaryField {
    static template = "hr_expense_stripe.MonetaryFieldBlankIfZero";

    get formattedValue() {
        if (!this.value) {
            return "";
        }

        return super.formattedValue;
    }

    get currencySymbol() {
        if (!this.value) {
            return "";
        }

        return super.currencySymbol;
    }
};

registry.category("fields").add("monetary_blank_if_zero", {
    ...monetaryField,
    component: MonetaryFieldBlankIfZero,
});
