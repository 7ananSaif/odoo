import {
    ProductConfiguratorDialog
} from '@sale/js/product_configurator_dialog/product_configurator_dialog';
import { patch } from '@web/core/utils/patch';

patch(ProductConfiguratorDialog, {
    props: {
        ...ProductConfiguratorDialog.props,
        start_date: { type: String, optional: true },
        end_date: { type: String, optional: true },
    },
});

patch(ProductConfiguratorDialog.prototype, {
    _getAdditionalRpcParams() {
        const params = super._getAdditionalRpcParams();
        if (this.props.start_date && this.props.end_date) {
            params.start_date = this.props.start_date;
            params.end_date = this.props.end_date;
        }
        return params;
    },
});
