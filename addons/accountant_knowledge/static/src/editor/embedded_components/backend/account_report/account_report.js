import { Component } from "@odoo/owl";
import { getEmbeddedProps } from "@html_editor/others/embedded_component_utils";
import { useService } from "@web/core/utils/hooks";

export class AccountReportComponent extends Component {
    static template = "accountant_knowledge.EmbeddedAccountReport";
    static props = {
        host: { type: Object },
        name: { type: String },
        options: { type: Object },
    };
    setup() {
        this.actionService = useService("action");
    }
    /** @returns {Promise} */
    openAccountReport() {
        return this.actionService.doAction({
            type: "ir.actions.client",
            tag: "account_report",
            name: this.props.name,
            params: {
                ignore_session: true,
                options: this.props.options,
            },
            context: {
                html_element_host_id: this.props.host.dataset.oeId,
                article_id: this.env.model.root.resId,
                report_id: this.props.options.report_id,
            },
        });
    }
}

export const accountReportEmbedding = {
    name: "accountReport",
    Component: AccountReportComponent,
    getProps: (host) => ({
        ...getEmbeddedProps(host),
        host,
    }),
};
