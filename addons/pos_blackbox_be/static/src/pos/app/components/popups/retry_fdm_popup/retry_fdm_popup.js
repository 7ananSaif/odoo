import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class RetryFdmPopup extends Component {
    static template = "point_of_sale.RetryFdmPopup";
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        message: { type: String, optional: true },
        retry: { type: Function, optional: true },
        downloadLogs: Function,
        close: Function,
    };

    onClickRetry() {
        this.props.retry();
        this.props.close();
    }
}
