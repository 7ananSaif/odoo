import { Component } from "@odoo/owl";
import { getEmbeddedProps } from "@html_editor/others/embedded_component_utils";

export class ReadonlyAccountReportComponent extends Component {
    static template = "accountant_knowledge.ReadonlyEmbeddedAccountReport";
    static props = {
        name: { type: String },
        options: { type: Object },
    };

}

export const readonlyAccountReportEmbedding = {
    name: "accountReport",
    Component: ReadonlyAccountReportComponent,
    getProps: (host) => ({
        ...getEmbeddedProps(host),
    }),
};
