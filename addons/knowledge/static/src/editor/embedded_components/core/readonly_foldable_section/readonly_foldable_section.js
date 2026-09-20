import {
    getEditableDescendants,
    getEmbeddedProps,
    useEditableDescendants,
} from "@html_editor/others/embedded_component_utils";
import { Component, useState } from "@odoo/owl";

export class ReadonlyFoldableSection extends Component {
    static template = "knowledge.ReadonlyEmbeddedFoldableSection";
    static props = {
        host: { type: Object },
        showContent: { type: Boolean, optional: true },
    };
    setup() {
        this.editableDescendants = useEditableDescendants(this.props.host);
        this.state = useState({
            showContent: this.props.showContent,
        });
    }
    onInputChange(ev) {
        this.state.showContent = ev.target.checked;
    }
}

export const readonlyFoldableSectionEmbedding = {
    name: "foldableSection",
    Component: ReadonlyFoldableSection,
    getProps: (host) => ({ host, ...getEmbeddedProps(host) }),
    getEditableDescendants: getEditableDescendants,
};
