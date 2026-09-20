import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

import { CreateTicketDialog } from "../components/create_ticket_dialog/create_ticket_dialog";

export class CreateTicket extends Interaction {
    static selector = ".create_ticket_forum";
    dynamicContent = {
        _root: {
            "t-on-click": this.onCreateTicketClick,
        },
    };

    setup() {
        this.forumId = parseInt(this.el.dataset.forumId);
        this.postId = parseInt(this.el.dataset.postId);
    }

    onCreateTicketClick() {
        this.services.dialog.add(CreateTicketDialog, {
            forumId: this.forumId,
            postId: this.postId,
        });
    }
}

registry
    .category("public.interactions")
    .add("website_helpdesk_forum.create_ticket", CreateTicket);
