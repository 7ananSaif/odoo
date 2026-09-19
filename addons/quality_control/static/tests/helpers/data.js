import { defineModels, fields, onRpc } from "@web/../tests/web_test_helpers";
import { SpreadsheetMixin } from "@spreadsheet/../tests/helpers/data";

class QualityCheckSpreadsheet extends SpreadsheetMixin {
    _name = "quality.check.spreadsheet";

    name = fields.Char();
    check_cell = fields.Char();

    _records = [
        {
            id: 1,
            name: "My quality check spreadsheet",
            spreadsheet_data: "{}",
            check_cell: "A1",
        },
        {
            id: 1111,
            name: "My quality check spreadsheet",
            spreadsheet_data: "{}",
            check_cell: "A1",
        },
    ];

    dispatch_spreadsheet_message() {}
}

onRpc(
    "/spreadsheet/data/<string:res_model>/<int:res_id>",
    function (_request, { res_model, res_id }) {
        const [record] = this.env[res_model].search_read([["id", "=", parseInt(res_id)]]);
        return {
            data: JSON.parse(record.spreadsheet_data),
            name: record.name,
            revisions: [],
            isReadonly: false,
            quality_check_display_name: "The check name",
            quality_check_cell: record.check_cell,
        };
    }
);

export function defineQualitySpreadsheetModels() {
    defineModels({
        QualityCheckSpreadsheet,
    });
}
