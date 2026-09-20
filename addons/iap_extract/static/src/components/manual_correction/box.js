import { Component, useState } from "@odoo/owl";

export class Box extends Component {
    static template = "iap_extract.Box";
    static props = {
        box: Object,
        pageWidth: String,
        pageHeight: String,
        onClickBoxCallback: Function,
    };
    /**
     * @override
     */
    setup() {
        this.state = useState(this.props.box);
    }

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    get style() {
        const style = [
            `left: calc(${this.state.midX} * ${this.props.pageWidth})`,
            `top: calc(${this.state.midY} * ${this.props.pageHeight})`,
            `width: calc(${this.state.width} * ${this.props.pageWidth})`,
            `height: calc(${this.state.height} * ${this.props.pageHeight})`,
            `transform: translate(-50%, -50%) rotate(${this.state.angle}deg)`,
            `-ms-transform: translate(-50%, -50%) rotate(${this.state.angle}deg)`,
            `-webkit-transform: translate(-50%, -50%) rotate(${this.state.angle}deg)`,
        ].join('; ');
        return style;
    }

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    onClick() {
        this.props.onClickBoxCallback(this.state.id, this.state.page);
    }
};
