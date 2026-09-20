import { _t } from "@web/core/l10n/translation";
import { constants, helpers } from "@odoo/o-spreadsheet";
import { OdooUIPlugin } from "@spreadsheet/plugins";

const { PIVOT_TABLE_CONFIG } = constants;
const uuidGenerator = new helpers.UuidGenerator();
const { sanitizeSheetName, getUniqueText } = helpers;

export class PivotOdooInsertion extends OdooUIPlugin {
    static getters = /** @type {const} */ ([]);

    /**
     * Handle a spreadsheet command
     * @param {Object} cmd Command
     */
    handle(cmd) {
        switch (cmd.type) {
            case "ADD_AND_INSERT_NEW_ODOO_PIVOT":
                this.addNewOdooPivot(cmd.pivotId, cmd.resModel, cmd.name);
                break;
        }
    }

    addNewOdooPivot(pivotId, resModel, pivotName) {
        this.dispatch("ADD_PIVOT", {
            pivotId,
            pivot: {
                type: "ODOO",
                model: resModel,
                name: pivotName,
                domain: [],
                context: {},
                columns: [],
                rows: [],
                measures: [],
                sortedColumn: undefined,
            },
        });
        const sheetId = uuidGenerator.smallUuid();
        const sheetIdFrom = this.getters.getActiveSheetId();
        const formulaId = this.getters.getPivotFormulaId(pivotId);
        const sheetName = this.getPivotDuplicateSheetName(
            _t("%(pivot_name)s (Pivot #%(pivot_id)s)", {
                pivot_name: pivotName,
                pivot_id: formulaId,
            })
        );
        this.dispatch("CREATE_SHEET", {
            sheetId,
            position: this.getters.getSheetIds().length,
            name: sheetName,
        });
        this.dispatch("ACTIVATE_SHEET", { sheetIdFrom, sheetIdTo: sheetId });
        this.dispatch("UPDATE_CELL", {
            sheetId,
            col: 0,
            row: 0,
            content: `=PIVOT("${formulaId}")`,
        });
        this.dispatch("CREATE_TABLE", {
            tableType: "dynamic",
            sheetId,
            ranges: [
                this.getters.getRangeDataFromZone(sheetId, {
                    left: 0,
                    top: 0,
                    right: 0,
                    bottom: 0,
                }),
            ],
            config: { ...PIVOT_TABLE_CONFIG },
        });
    }

    getPivotDuplicateSheetName(sheetName) {
        const names = this.getters.getSheetIds().map((id) => this.getters.getSheetName(id));
        const sanitizedName = sanitizeSheetName(sheetName);
        return getUniqueText(sanitizedName, names);
    }
}
