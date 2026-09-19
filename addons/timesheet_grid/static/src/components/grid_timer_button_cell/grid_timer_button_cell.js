import { Component } from "@odoo/owl";

export class GridTimerButtonCell extends Component {
    static template = "timesheet_grid.GridTimerButtonCell";
    static props = {
        hotKey: { type: String, optional: true },
        row: Object,
        addTimeMode: Boolean,
        hovered: { type: Boolean, optional: true },
        timerRunning: { type: Boolean, optional: true },
        onTimerClick: Function,
    };
}
