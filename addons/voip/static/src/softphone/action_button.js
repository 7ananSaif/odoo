import { Component } from "@odoo/owl";

/**
 * Generic component that defines the general structure of an action button.
 */
export class ActionButton extends Component {
    static defaultProps = { extraClass: "", type: "secondary" };
    static props = {
        extraClass: { type: String, optional: true },
        hideLabel: { type: Boolean, optional: true },
        icon: String,
        name: { type: String, optional: true },
        onClick: Function,
        title: { type: String, optional: true },
        type: { type: String, optional: true },
        inCallPad: { type: Boolean, optional: true },
        disabled: { type: Boolean, optional: true },
        isSmall: { type: Boolean, optional: true },
    };
    static template = "voip.ActionButton";

    /**
     * Displays the right icon library class depending on the icon defined in
     * the prop.
     *
     * @returns {"fa"|"oi"}
     */
    get iconLib() {
        if (this.props.icon.startsWith("oi-")) {
            return "oi";
        }
        return "fa";
    }
}
