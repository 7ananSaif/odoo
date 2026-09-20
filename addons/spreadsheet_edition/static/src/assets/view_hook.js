import { _t } from "@web/core/l10n/translation";
import { useBus, useService } from "@web/core/utils/hooks";
import { SpreadsheetSelectorDialog } from "./components/spreadsheet_selector_dialog/spreadsheet_selector_dialog";
import { user } from "@web/core/user";
import { omit } from "@web/core/utils/objects";

export function useInsertInSpreadsheet(env, getExportableFields) {
    const { config, bus, model, searchModel } = env;
    useBus(bus, "insert-in-spreadsheet", async () => {
        _openSpreadsheetSelectorDialog();
    });
    const action = useService("action");
    const _getColumnsForSpreadsheet = () => {
        const fields = model.root.fields;
        const columns = getExportableFields();
        return columns
            .filter((col) => !["binary", "json"].includes(fields[col.name].type))
            .map((col) => {
                const field = fields[col.name];
                return { name: col.name, type: field.type, string: field.string };
            });
    };

    const _getListForSpreadsheet = async (name) => {
        const root = model.root;
        const { actionId } = config;
        const { xml_id } = actionId ? await action.loadAction(actionId, model.root.context) : {};
        const fields = root.fields;

        return {
            list: {
                model: root.resModel,
                domain: searchModel.domainString,
                orderBy: root.orderBy.filter((field) => fields[field.name]),
                context: omit(root.context, ...Object.keys(user.context)),
                columns: _getColumnsForSpreadsheet(),
                name,
                actionXmlId: xml_id,
            },
            fields,
        };
    };

    const _openSpreadsheetSelectorDialog = async () => {
        const root = model.root;
        const count = root.groups
            ? root.groups.reduce((acc, group) => group.count + acc, 0)
            : root.count;
        const selection = await root.getResIds(true);
        const threshold = selection.length > 0 ? selection.length : Math.min(count, root.limit);
        let name = config.getDisplayName();
        const sortBy = root.orderBy[0];
        if (sortBy && root.fields[sortBy.name]) {
            name = _t("%(field name)s by %(order)s", {
                "field name": name,
                order: root.fields[sortBy.name].string,
            });
        }
        const { list, fields } = await _getListForSpreadsheet(name);

        // if some records are selected, we replace the domain with a "id in [selection]" clause
        if (selection.length > 0) {
            list.domain = [["id", "in", selection]];
        }
        const actionOptions = {
            preProcessingAsyncAction: "insertList",
            preProcessingAsyncActionData: { list, threshold, fields },
        };

        const params = {
            threshold,
            type: "LIST",
            name,
            actionOptions,
        };
        root.model.dialog.add(SpreadsheetSelectorDialog, params);
    };

    return _openSpreadsheetSelectorDialog;
}
