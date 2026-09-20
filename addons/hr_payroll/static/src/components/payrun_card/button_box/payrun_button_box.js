import { onWillStart, onWillRender, Component } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

export class PayRunButtonBox extends Component {
    static template = "hr_payroll.PayRunButtonBox";
    static components = {
        Dropdown,
        DropdownItem,
    };
    static props = {
        slots: { type: Object, optional: true },
        class: { type: String, optional: true },
    };
    static defaultProps = {
        slots: {},
        class: "",
    };

    setup() {
        this.ui = useService("ui");
        this.cacheAllowedGroups = [];
        onWillStart(async () => {
            if (Object.values(this.props.slots).some((slot) => slot.group)) {
                await this.computeAllowedGroups(this.props.slots);
            }
        });
        onWillRender(() => {
            this.computeAllowedButtons(this.props.slots, this.cacheAllowedGroups);
        });
    }

    async computeAllowedGroups(slots) {
        for (const [, slot] of Object.entries(slots)) {
            if (!slot.group || this.cacheAllowedGroups.includes(slot.group)) {
                continue;
            }
            if (await user.hasGroup(slot.group)) {
                this.cacheAllowedGroups.push(slot.group);
            }
        }
    }

    computeAllowedButtons(slots, cacheAllowedGroups = []) {
        const maxVisibleButtons = [0, 0, 0, 1, 1, 2, 2][this.ui.size] ?? 0;
        const allVisibleButtons = Object.entries(slots).map(([slotName, slot]) => {
            if (!slot.isVisible) {
                return null;
            }
            return !slot.group || cacheAllowedGroups.includes(slot.group) ? [slotName, slot] : null;
        });

        const [priorityVisibleActionButtons, normalVisibleActionButtons, smartButtonsVisible] =
            allVisibleButtons.filter(Boolean).reduce(
                ([priority, normal, smart], [slotName, slot]) => {
                    if (slot.isPriority) {
                        priority.push(slotName);
                    } else if (slot.isSmartButton) {
                        smart.push(slotName);
                    } else {
                        normal.push(slotName);
                    }
                    return [priority, normal, smart];
                },
                [[], [], []]
            );

        this.allSmartButtons = smartButtonsVisible;
        const allVisibleActionButtons = [
            ...priorityVisibleActionButtons,
            ...normalVisibleActionButtons,
        ];
        switch (maxVisibleButtons) {
            case 1:
                this.visibleActionButtons = allVisibleActionButtons.slice(0, 1);
                this.additionalActionButtons = allVisibleActionButtons.slice(1);
                break;
            case 2:
                if (priorityVisibleActionButtons.length > 0) {
                    this.visibleActionButtons = allVisibleActionButtons.slice(0, 2);
                    this.additionalActionButtons = allVisibleActionButtons.slice(2);
                } else {
                    this.visibleActionButtons = allVisibleActionButtons.slice(0, 1);
                    this.additionalActionButtons = allVisibleActionButtons.slice(1);
                }
                break;
            default:
                this.visibleActionButtons = [];
                this.additionalActionButtons = allVisibleActionButtons;
        }
    }
}
