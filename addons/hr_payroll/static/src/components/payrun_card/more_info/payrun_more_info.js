import { Component, onWillStart, onWillRender } from "@odoo/owl";
import { Field } from "@web/views/fields/field";
import { Dialog } from "@web/core/dialog/dialog";
import { usePopover } from "@web/core/popover/popover_hook";
import { user } from "@web/core/user";

export class MoreInfo extends Component {
    static template = "hr_payroll.MoreInfo";
    static props = {
        slots: { type: Object, optional: true },
    };
    static defaultProps = {
        slots: {},
    };

    setup() {
        this.moreInfoCard = usePopover(MoreInfoCardPopover);
        this.cacheAllowedGroups = [];
        onWillStart(async () => {
            if (Object.values(this.props.slots).some((slot) => slot.group)) {
                await this.computeAllowedGroups(this.props.slots);
            }
        });
        onWillRender(() => {
            this.computeMoreInfo(this.props.slots, this.cacheAllowedGroups);
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

    computeMoreInfo(slots, cacheAllowedGroups = []) {
        const result = Object.entries(slots).map(([slotName, slot]) => {
            if (!slot.isVisible) {
                return null;
            }
            return !slot.group || cacheAllowedGroups.includes(slot.group) ? [slotName, slot] : null;
        });
        this.allowedSlots = Object.fromEntries(result.filter(Boolean));
    }

    onClickMoreInfo(ev) {
        if (!this.moreInfoCard.isOpen) {
            this.moreInfoCard.open(ev.currentTarget, {
                slots: this.allowedSlots,
            });
        }
    }

    async hasGroup(group) {
        return group ? user.hasGroup(group) : true;
    }
}

export class MoreInfoCardPopover extends Component {
    static template = "hr_payroll.MoreInfoCardPopover";
    static subTemplates = {
        popover: "hr_payroll.MoreInfoCardPopover.popover",
        body: "hr_payroll.MoreInfoCardPopover.body",
    };
    static props = {
        slots: { type: Object, optional: true },
        close: { type: Function, optional: true },
    };
    static components = {
        Field,
        Dialog,
    };
}
