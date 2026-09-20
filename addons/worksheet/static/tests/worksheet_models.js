import { defineModels, models, fields } from "@web/../tests/web_test_helpers";

import { mailModels } from "@mail/../tests/mail_test_helpers";

export class WorksheetTemplate extends models.Model {
    hex_color = fields.Char();

    _records = [{ id: 1, hex_color: "#ff4444" }];
}

export function defineWorksheetModels() {
    defineModels({ ...mailModels, WorksheetTemplate });
}
