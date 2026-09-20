import { Component, onWillUnmount } from "@odoo/owl";
import {
    registries,
    stores,
    ClientDisconnectedError,
} from "@spreadsheet/o_spreadsheet/o_spreadsheet";
import { usePopover } from "@web/core/popover/popover_hook";
import { _t } from "@web/core/l10n/translation";

const { useStore, ClientFocusStore } = stores;
const { topbarComponentRegistry } = registries;

const SHOWN_USER_THUMBNAIL = 10;

class SpreadsheetUsersTooltip extends Component {
    static template = "spreadsheet_edition.SpreadsheetUsersTooltip";
    static props = {
        users: Object,
        onMouseLeave: Function,
        onMouseEnter: Function,
        onClick: Function,
        close: { optional: true, type: Function },
    };

    getDataTooltip(userName) {
        return _t("Go to %(userName)s", { userName });
    }
}

export class CollaborativeStatus extends Component {
    static template = "spreadsheet_edition.CollaborativeStatus";
    static props = {};

    setup() {
        super.setup();
        this.popover = usePopover(SpreadsheetUsersTooltip, { position: "bottom" });
        this.clientFocusStore = useStore(ClientFocusStore);

        onWillUnmount(() => {
            if (this.timeoutId) {
                clearTimeout(this.timeoutId);
            }
        });
    }

    jumpToUser(user) {
        this.clientFocusStore.jumpToClient(user.clientId);
    }

    get connectedUsers() {
        const connectedUsers = [];
        let currentClientId;
        try {
            currentClientId = this.env.model.getters.getCurrentClient().id;
        } catch (error) {
            if (error instanceof ClientDisconnectedError) {
                // We are currently disconnecting
                return connectedUsers;
            }
            throw error;
        }
        for (const client of this.env.model.getters.getConnectedClients()) {
            if (
                client.id !== currentClientId &&
                !connectedUsers.some((user) => user.id === client.userId)
            ) {
                connectedUsers.push({
                    id: client.userId,
                    name: client.name,
                    avatar: `/web/image?model=res.users&field=avatar_128&id=${client.userId}`,
                    clientId: client.id,
                    color: client.color,
                });
            }
        }
        return connectedUsers;
    }

    get usersThumbnail() {
        return this.connectedUsers.slice(0, SHOWN_USER_THUMBNAIL);
    }

    get tooltipInfo() {
        return this.connectedUsers.slice(SHOWN_USER_THUMBNAIL);
    }

    getDataTooltip(userName) {
        return _t("Go to %(userName)s", { userName });
    }

    openPopover(ev) {
        if (this.timeoutId) {
            clearTimeout(this.timeoutId);
        } else {
            this.popover.open(ev.currentTarget, {
                users: this.tooltipInfo,
                onMouseEnter: this.openPopover.bind(this),
                onMouseLeave: this.closePopover.bind(this),
                onClick: this.jumpToUser.bind(this),
            });
            this.clientFocusStore.showClientTag();
        }
    }

    closePopover(ev) {
        this.timeoutId = setTimeout(() => this.cleanupPopover(), 300);
    }

    cleanupPopover() {
        this.timeoutId = undefined;
        this.popover.close();
        this.clientFocusStore.hideClientTag();
    }

    showUser(user) {
        this.clientFocusStore.focusClient(user.clientId);
    }

    hideUser(user) {
        this.clientFocusStore.unfocusClient(user.clientId);
    }
}

topbarComponentRegistry.add("collaborative_status", {
    component: CollaborativeStatus,
    sequence: 10,
});
