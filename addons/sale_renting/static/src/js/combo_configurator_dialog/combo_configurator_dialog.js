import {
    ComboConfiguratorDialog
} from '@sale/js/combo_configurator_dialog/combo_configurator_dialog';
import { patch } from '@web/core/utils/patch';

patch(ComboConfiguratorDialog, {
    props: {
        ...ComboConfiguratorDialog.props,
        start_date: { type: String, optional: true },
        end_date: { type: String, optional: true },
    },
});

patch(ComboConfiguratorDialog.prototype, {
    _getAdditionalRpcParams() {
        const params = super._getAdditionalRpcParams();
        if (this.props.start_date && this.props.end_date) {
            params.start_date = this.props.start_date;
            params.end_date = this.props.end_date;
        }
        return params;
    },

    _getAdditionalDialogProps() {
        const props = super._getAdditionalDialogProps();
        if (this.props.start_date && this.props.end_date) {
            props.start_date = this.props.start_date;
            props.end_date = this.props.end_date;
        }
        return props;
    },
});
