import { Component, useState, onWillUnmount } from "@odoo/owl";
import { usePrepDisplay } from "@pos_enterprise/app/services/preparation_display_service";
import { Orderline } from "@pos_enterprise/app/components/orderline/orderline";
import { computeFontColor, useDelayedValueChange } from "@pos_enterprise/app/utils/utils";
import { TagsList } from "@web/core/tags_list/tags_list";
import { logPosMessage } from "@point_of_sale/app/utils/pretty_console_log";

export class Order extends Component {
    static components = { Orderline, TagsList };
    static template = "pos_enterprise.Order";
    static props = {
        order: Object,
    };

    setup() {
        this.prepDisplay = usePrepDisplay();
        this.state = useState({
            duration: 0,
            productHighlighted: [],
            changeStageTimeout: null,
        });
        this.actionInProgress = false;
        this._updateDuration();
        this.interval = setInterval(() => {
            this._updateDuration();
        }, 1000);
        onWillUnmount(() => {
            clearInterval(this.interval);
        });

        this.internalNoteState = useDelayedValueChange(() => this.order.pos_order_id.internal_note);
    }

    clearChangeTimeout() {
        clearTimeout(this.state.changeStageTimeout);
        this.state.changeStageTimeout = null;
    }

    _updateDuration() {
        this.state.duration = this._computeDuration();
    }
    get order() {
        return this.props.order.prepOrder;
    }
    get presetTime() {
        return this.order.pos_order_id.preset_time.toFormat("HH:mm");
    }

    get presetDate() {
        return this.order.pos_order_id.preset_time.toFormat("dd/MM");
    }

    get fontColor() {
        return computeFontColor(this.props.order.stage.color);
    }

    getChildPreparationLineStates(orderline_id) {
        return this.props.order.states.filter(
            (pl) => pl.prep_line_id.combo_parent_id?.id === orderline_id.id
        );
    }

    get orderlines() {
        const orderlines = [];
        for (const sate of this.props.order.states) {
            if (orderlines.includes(sate)) {
                continue;
            }
            const parent_preparation_line = sate.prep_line_id.combo_parent_id;
            if (parent_preparation_line) {
                const children = this.getChildPreparationLineStates(parent_preparation_line);
                const allChildrenAreFalse = children.every((child) => child.todo === false);
                orderlines.push(
                    { prep_line_id: parent_preparation_line, todo: !allChildrenAreFalse },
                    ...children
                );
            } else {
                orderlines.push(sate);
            }
        }
        return orderlines;
    }

    _computeDuration() {
        const timeDiff = this._getOrderDuration();
        if (timeDiff > this.props.order.stage.alert_timer) {
            this.isAlert = true;
        } else {
            this.isAlert = false;
        }

        return timeDiff;
    }

    changeOrderlineStatus(state) {
        const lastStage = this.prepDisplay.lastStage.id;
        if (this.props.order.stage.id === lastStage) {
            return;
        }
        const newState = !state.todo;
        state.todo = newState;
        if (state.prep_line_id.combo_line_ids.length > 0) {
            this.getChildPreparationLineStates(state.prep_line_id).forEach((state_line) => {
                state_line.todo = newState;
            });
        }

        if (this.props.order.states.some((state) => state.todo)) {
            this.prepDisplay.syncStateStatus(this.props.order.states);
        } else {
            this.changeStateStageAnimation(this.props.order.states);
        }
    }

    _getOrderDuration() {
        return Math.max(...this.props.order.states.map((state) => state.computeDuration()));
    }

    async doneOrder() {
        this.prepDisplay.doneOrders(this.props.order.states);
    }

    get cardColor() {
        return "o_pdis_card_color_0";
    }

    async clickOrder() {
        if (this.actionInProgress) {
            return;
        }
        try {
            this.actionInProgress = true;
            if (this.props.order.stage === this.prepDisplay.lastStage) {
                return;
            } else {
                const strickedLine = this.props.order.states.filter((l) => !l.todo);

                await this.changeStateStageAnimation(
                    strickedLine.length ? strickedLine : this.props.order.states
                );
            }
        } catch (error) {
            logPosMessage("Order", "clickOrder", "Error clicking order", false, [error]);
        } finally {
            this.actionInProgress = false;
        }
    }
    get pdisNotes() {
        return JSON.parse(this.order.pos_order_id.internal_note || "[]");
    }
    async changeStateStageAnimation(states) {
        if (states.length === this.props.order.states.length) {
            this.state.changeStageTimeout = setTimeout(async () => {
                this.lastStageChange = await this.prepDisplay.changeStateStage(states);
                this.clearChangeTimeout();
            }, 250);
        } else {
            this.lastStageChange = await this.prepDisplay.changeStateStage(states);
        }
    }
}
