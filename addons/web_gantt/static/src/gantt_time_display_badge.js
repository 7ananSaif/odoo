import { Component } from "@odoo/owl";

export class GanttTimeDisplayBadge extends Component {
    static props = {
        reactive: {
            type: Object,
            shape: {
                position: {
                    type: Object,
                    shape: {
                        top: { type: Number, optional: true },
                        right: { type: Number, optional: true },
                        left: { type: Number, optional: true },
                    },
                    optional: true,
                },
                class: { type: String, optional: true },
                text: { type: String, optional: true },
            },
        },
    };
    static template = "web_gantt.GanttTimeDisplayBadge";

    get positionStyle() {
        const { position } = this.props.reactive;
        const style = [`top:${position.top}px`];
        if ("left" in position) {
            style.push(`left:${position.left}px`);
        } else {
            style.push(`right:${position.right}px`);
        }
        return style.join(";");
    }
}
