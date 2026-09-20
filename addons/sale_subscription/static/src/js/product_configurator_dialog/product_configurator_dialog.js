import {
    ProductConfiguratorDialog
} from '@sale/js/product_configurator_dialog/product_configurator_dialog';
import { patch } from '@web/core/utils/patch';

patch(ProductConfiguratorDialog, {
    props: {
        ...ProductConfiguratorDialog.props,
        plan_id: { type: Number, optional: true },
    },
});

patch(ProductConfiguratorDialog.prototype, {
    _getAdditionalRpcParams() {
        const params = super._getAdditionalRpcParams();
        if (this.props.plan_id) {
            params.plan_id = this.props.plan_id;
        }
        return params;
    },
});
