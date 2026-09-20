import {onWillRender} from "@odoo/owl";
import {ButtonBox} from "@web/views/form/button_box/button_box";
import {useService} from "@web/core/utils/hooks";

export class PayRunButtonBox extends ButtonBox {
    static template = "hr_payroll.PayRunCard.ButtonBox";

    setup() {
        const ui = useService("ui");
        onWillRender(() => {
            const maxVisibleButtons= [0, 0, 0, 0, 1, 1, 1][ui.size] ?? 1;
            const allVisibleActionButtons = Object.entries(this.props.slots)
                .filter(([_, slot]) => this.isSlotVisible(slot) && !this.isSmartButton(slot))
                .map(([slotName]) => slotName);
            
            if (allVisibleActionButtons.length <= maxVisibleButtons) {
                this.visibleActionButtons = allVisibleActionButtons;
                this.additionalActionButtons = [];
                this.isFull = allVisibleActionButtons.length === maxVisibleButtons;
            } else {
                // -1 for 3 dots dropdown
                const splitIndex = Math.max(maxVisibleButtons, 0);
                this.visibleActionButtons = allVisibleActionButtons.slice(0, splitIndex);
                this.additionalActionButtons = allVisibleActionButtons.slice(splitIndex);
                this.isFull = true;
            }
            this.allSmartButtons = Object.entries(this.props.slots)
                .filter(([, slot]) => this.isSlotVisible(slot) && this.isSmartButton(slot))
                .map(([slotName]) => slotName);
        });
    }

    isSmartButton(slot) {
        return !("isSmartButton" in slot) || slot.isSmartButton;
    }
}
