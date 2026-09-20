import { SaleOrderLineProductField } from '@sale/js/sale_product_field';
import { serializeDateTime } from "@web/core/l10n/dates";
import { patch } from '@web/core/utils/patch';

patch(SaleOrderLineProductField.prototype, {
    _getAdditionalRpcParams() {
        const params = super._getAdditionalRpcParams();
        const { rental_start_date, rental_return_date } = this.props.record.model.root.data;
        if (rental_start_date && rental_return_date) {
            params.start_date = serializeDateTime(rental_start_date);
            params.end_date = serializeDateTime(rental_return_date);
        }
        return params;
    },

    _getAdditionalDialogProps() {
        const props = super._getAdditionalDialogProps();
        const { rental_start_date, rental_return_date } = this.props.record.model.root.data;
        if (rental_start_date && rental_return_date) {
            props.start_date = serializeDateTime(rental_start_date);
            props.end_date = serializeDateTime(rental_return_date);
        }
        return props;
    },

    get m2oProps() {
        const props = super.m2oProps;
        return {
            ...props,
            context: { ...props.context, show_rental_tag: props.context.in_rental_app },
        };
    },
});
