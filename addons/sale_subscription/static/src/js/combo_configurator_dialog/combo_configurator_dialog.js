import {
    ComboConfiguratorDialog
} from '@sale/js/combo_configurator_dialog/combo_configurator_dialog';
import { patch } from '@web/core/utils/patch';

patch(ComboConfiguratorDialog, {
    props: {
        ...ComboConfiguratorDialog.props,
        plan_id: { type: Number, optional: true },
    },
});

patch(ComboConfiguratorDialog.prototype, {
    _getAdditionalRpcParams() {
        const params = super._getAdditionalRpcParams();
        if (this.props.plan_id) {
            params.plan_id = this.props.plan_id;
        }
        return params;
    },

    _getAdditionalDialogProps() {
        const props = super._getAdditionalDialogProps();
        if (this.props.plan_id) {
            props.plan_id = this.props.plan_id;
        }
        return props;
    },
});
