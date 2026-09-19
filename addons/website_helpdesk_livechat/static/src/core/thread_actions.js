import { registerThreadAction } from "@mail/core/common/thread_actions";
import "@mail/discuss/call/common/thread_actions";

import { LivechatCommandDialog } from "@im_livechat/core/common/livechat_command_dialog";

import { _t } from "@web/core/l10n/translation";
import { usePopover } from "@web/core/popover/popover_hook";

registerThreadAction("create-ticket", {
    actionPanelComponent: LivechatCommandDialog,
    actionPanelComponentProps: ({ action }) => ({
        close: () => action.close(),
        commandName: "ticket",
        placeholderText: _t("e.g. Product arrived damaged"),
        title: _t("Create Ticket"),
        icon: "fa fa-life-ring",
    }),
    close: ({ action }) => action.popover?.close(),
    condition: false, // managed by ThreadAction patch
    panelOuterClass: "bg-100",
    icon: "fa fa-life-ring fa-fw",
    name: _t("Create Ticket"),
    sequence: 15,
    sequenceGroup: 25,
    setup({ owner }) {
        if (!owner.env.inChatWindow) {
            this.popover = usePopover(LivechatCommandDialog, {
                onClose: () => this.close(),
                popoverClass: this.panelOuterClass,
            });
        }
    },
    toggle: true,
    open({ owner, thread }) {
        this.popover?.open(owner.root.el.querySelector(`[name="${this.id}"]`), {
            thread,
            ...this.actionPanelComponentProps,
        });
    },
});
