import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

export class HolderEndDialog extends Component {
    static template = "equity.HolderEndDialog";
    static components = { Dialog };
    static props = {
        ubo: { type: Object },
        close: { type: Function },
    };

    setup() {
        this.state = useState({
            ubo: this.props.ubo,
            endDate: this.props.ubo["end_date"],
        });
    }

    confirm() {
        this.state.ubo["end_date"] = this.state.endDate;
        this.props.close();
    }

    get title() {
        return _t("Function end: %s", this.state.ubo["holder_id"]["name"]);
    }
}
