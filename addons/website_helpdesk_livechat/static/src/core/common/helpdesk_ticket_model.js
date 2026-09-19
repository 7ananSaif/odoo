import { fields, Record } from "@mail/core/common/record";
import { router } from "@web/core/browser/router";

export class HelpdeskTicket extends Record {
    static id = "id";
    static _name = "helpdesk.ticket";

    /** @type {number} */
    id;
    /** @type {string} */
    name;
    href = fields.Attr("", {
        compute() {
            return router.stateToUrl({ model: 'helpdesk.ticket', resId: this.id });
        }
    });
}

HelpdeskTicket.register();
