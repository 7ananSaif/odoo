import { Record } from "@mail/core/common/record";

export class WhatsAppAccount extends Record {
    static id = "id";
    static _name = "whatsapp.account";

    /** @type {number} */
    id;
    /** @type {string} */
    name;
}

WhatsAppAccount.register();
