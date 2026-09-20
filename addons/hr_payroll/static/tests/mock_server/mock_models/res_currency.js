import { models } from "@web/../tests/web_test_helpers";

export class ResCurrency extends models.ServerModel {
    _name = "res.currency";

    _records = [
        { id: 1, name: "USD", symbol: "$", position: "before" },
        { id: 2, name: "EUR", symbol: "€", position: "after" },
    ];
}
