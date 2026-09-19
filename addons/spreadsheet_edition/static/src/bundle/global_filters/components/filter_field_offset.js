import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class FilterFieldOffset extends Component {
    static template = "spreadsheet_edition.FilterFieldOffset";
    static props = {
        onOffsetSelected: Function,
        selectedOffset: Number,
        active: Boolean,
    };

    /**
     * @param {Event & { target: HTMLSelectElement }} ev
     */
    onOffsetSignChanged(ev) {
        const newOffsetSign = parseInt(ev.target.value);
        if (newOffsetSign && this.props.selectedOffset === 0) {
            this.props.onOffsetSelected(newOffsetSign);
        } else {
            this.props.onOffsetSelected(newOffsetSign * Math.abs(this.props.selectedOffset));
        }
    }

    /**
     * @param {Event & { target: HTMLSelectElement }} ev
     */
    onOffsetSelected(ev) {
        let newOffset = Math.abs(parseInt(ev.target.value));
        if (newOffset > 50) {
            // We limit the offset to 50 to avoid having
            // a too big offset that would result in an
            // invalid date.
            newOffset = 50;
        }
        this.props.onOffsetSelected(this.offsetSign * newOffset);
    }

    get title() {
        return this.props.active
            ? _t("Period offset applied to this source")
            : _t("Requires a selected field");
    }

    get offsetSign() {
        if (!this.props.selectedOffset) {
            return 0;
        }
        return this.props.selectedOffset < 0 ? -1 : 1;
    }
}
