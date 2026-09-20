import { Message } from "@mail/core/common/message";

import { markup } from "@odoo/owl";

import { createDocumentFragmentFromContent, setElementContent } from "@web/core/utils/html";
import { patch } from "@web/core/utils/patch";

function addNewTicketsToMessage(oldMessage, newElement) {
    const parsedDoc = createDocumentFragmentFromContent(oldMessage);
    const loadMoreDiv = parsedDoc.querySelector(".o_load_more");
    if (loadMoreDiv) {
        loadMoreDiv.parentElement.removeChild(loadMoreDiv);
    }
    const tempContainer = parsedDoc.createElement("div");
    setElementContent(tempContainer, newElement);
    const bodyElement = parsedDoc.querySelector(".o_mail_notification");
    while (tempContainer.firstChild) {
        bodyElement.appendChild(tempContainer.firstChild);
    }
    return markup(parsedDoc.documentElement.outerHTML);
}

patch(Message.prototype, {
    async loadMoreTickets(message, listKeywords, loadCounter) {
        const ticketsHTML = await this.env.services.orm.call(
            "discuss.channel",
            "fetch_ticket_by_keyword",
            [this.props.message.resId],
            {
                list_keywords: listKeywords.split(" "),
                load_counter: parseInt(loadCounter),
            }
        );
        message.body = addNewTicketsToMessage(message.body, markup(ticketsHTML));
    },
    onClick(ev) {
        const { oeLst, oeLoadCounter, oeType } = ev.target.dataset;
        if (oeType == "load") {
            this.loadMoreTickets(this.props.message, oeLst, oeLoadCounter);
            return;
        }
        super.onClick(ev);
    },
});
