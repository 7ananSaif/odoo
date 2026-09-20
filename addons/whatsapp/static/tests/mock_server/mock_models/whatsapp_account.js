import { models } from "@web/../tests/web_test_helpers";

export class WhatsAppAccount extends models.ServerModel {
    _name = "whatsapp.account";

    _records = [{ id: 1, name: "Test Account" }];
}
