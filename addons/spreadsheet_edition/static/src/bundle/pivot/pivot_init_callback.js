//@ts-check

import { helpers, stores } from "@odoo/o-spreadsheet";
import { OdooPivot } from "@spreadsheet/pivot/odoo_pivot";
import { Domain } from "@web/core/domain";
import { deepCopy } from "@web/core/utils/objects";
import { _t } from "@web/core/l10n/translation";

const uuidGenerator = new helpers.UuidGenerator();
const { parseDimension, isDateOrDatetimeField, sanitizeSheetName, pivotTimeAdapter } = helpers;

const { SidePanelStore } = stores;

/**
 * Asserts that the given result is successful, otherwise throws an error.
 *
 * @param {import("@odoo/o-spreadsheet").DispatchResult} result
 */
function ensureSuccess(result) {
    if (!result.isSuccessful) {
        throw new Error(`Couldn't insert pivot in spreadsheet. Reasons : ${result.reasons}`);
    }
}

function addEmptyGranularity(dimensions, fields) {
    return dimensions.map((dimension) => {
        if (isDateOrDatetimeField(fields[dimension.fieldName])) {
            return {
                granularity: "month",
                ...dimension,
            };
        }
        return dimension;
    });
}

export function insertPivot(pivotData) {
    const fields = pivotData.metaData.fields;
    const activeMeasures = pivotData.metaData.activeMeasures;
    const measures = activeMeasures.map((measure) => ({
        id: fields[measure]?.aggregator ? `${measure}:${fields[measure].aggregator}` : measure,
        fieldName: measure,
        aggregator: fields[measure]?.aggregator,
    }));
    /** @type {import("@spreadsheet").OdooPivotCoreDefinition} */
    const pivot = deepCopy({
        type: "ODOO",
        domain: new Domain(pivotData.searchParams.domain).toJson(),
        context: pivotData.searchParams.context,
        measures,
        model: pivotData.metaData.resModel,
        columns: addEmptyGranularity(
            pivotData.metaData.fullColGroupBys.map(parseDimension),
            fields
        ),
        rows: addEmptyGranularity(pivotData.metaData.fullRowGroupBys.map(parseDimension), fields),
        name: pivotData.name,
        actionXmlId: pivotData.actionXmlId,
    });
    /**
     * @param {import("@spreadsheet").OdooSpreadsheetModel} model
     */
    return async (model, stores) => {
        const sortedMeasure = pivotData.metaData.sortedColumn?.measure;
        const sortedColumn = activeMeasures.includes(sortedMeasure)
            ? getPivotSortedColumn(model, pivotData)
            : undefined;
        if (sortedColumn) {
            pivot.sortedColumn = sortedColumn;
        }
        const pivotId = uuidGenerator.smallUuid();
        ensureSuccess(
            model.dispatch("ADD_PIVOT", {
                pivotId,
                pivot,
            })
        );
        const ds = model.getters.getPivot(pivotId);
        if (!(ds instanceof OdooPivot)) {
            throw new Error("The pivot data source is not an OdooPivot");
        }
        await ds.load();

        let sheetName = sanitizeSheetName(
            _t("%(pivot_name)s (Pivot #%(pivot_id)s)", {
                pivot_name: pivot.name,
                pivot_id: model.getters.getPivotFormulaId(pivotId),
            })
        );
        // Add an empty sheet in the case of an existing spreadsheet.
        if (!this.isEmptySpreadsheet) {
            const sheetId = uuidGenerator.smallUuid();
            const sheetIdFrom = model.getters.getActiveSheetId();
            if (model.getters.getSheetIdByName(sheetName)) {
                sheetName = undefined;
            }
            model.dispatch("CREATE_SHEET", {
                sheetId,
                position: model.getters.getSheetIds().length,
                name: sheetName,
            });
            model.dispatch("ACTIVATE_SHEET", { sheetIdFrom, sheetIdTo: sheetId });
        } else {
            const sheetId = model.getters.getActiveSheetId();
            model.dispatch("RENAME_SHEET", {
                sheetId,
                oldName: model.getters.getSheetName(sheetId),
                newName: sheetName,
            });
        }
        const sheetId = model.getters.getActiveSheetId();

        const table = ds.getExpandedTableStructure();
        ensureSuccess(
            model.dispatch("INSERT_PIVOT_WITH_TABLE", {
                sheetId,
                col: 0,
                row: 0,
                pivotId,
                table: table.export(),
                pivotMode: "static",
            })
        );

        const columns = [];
        for (let col = 0; col <= table.columns[table.columns.length - 1].length; col++) {
            columns.push(col);
        }
        model.dispatch("AUTORESIZE_COLUMNS", { sheetId, cols: columns });
        const sidePanel = stores.get(SidePanelStore);
        sidePanel.open("PivotSidePanel", { pivotId });
    };
}

function getPivotSortedColumn(model, pivotData) {
    if (!pivotData.metaData.sortedColumn) {
        return undefined;
    }

    const fields = pivotData.metaData.fields;
    const sortedValues = pivotData.metaData.sortedColumn.groupId[1];
    const sortColDomain = [];
    let currentBranch = pivotData.colGroupTree;

    for (let i = 0; i < sortedValues.length; i++) {
        let value = sortedValues[i];
        currentBranch = currentBranch.directSubTrees.get(value);
        const field = pivotData.metaData.fullColGroupBys[i];
        if (!field) {
            return undefined;
        }

        const [fieldName, granularity] = field.split(":");
        const fieldType = fields[fieldName].type;
        if (fieldType === "date" || fieldType === "datetime") {
            const normalizer = pivotTimeAdapter(granularity).normalizeServerValue;
            const readGroupResult = {
                [field]: [currentBranch.root.values.at(-1), currentBranch.root.labels.at(-1)],
            };
            const locale = model.getters.getLocale();
            value = normalizer(field, fields[fieldName], readGroupResult, locale);
        }

        sortColDomain.push({ value, field, type: fieldType });
    }

    const sortedColumn = pivotData.metaData.sortedColumn;
    const measure = sortedColumn.measure;
    return {
        domain: sortColDomain,
        order: sortedColumn.order,
        measure: fields[measure]?.aggregator ? `${measure}:${fields[measure].aggregator}` : measure,
    };
}
