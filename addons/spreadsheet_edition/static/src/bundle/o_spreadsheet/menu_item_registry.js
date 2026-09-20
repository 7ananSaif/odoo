import { _t } from "@web/core/l10n/translation";
import { registries, stores } from "@odoo/o-spreadsheet";
import { REINSERT_LIST_CHILDREN } from "../list/list_actions";
import {
    REINSERT_DYNAMIC_PIVOT_CHILDREN,
    REINSERT_STATIC_PIVOT_CHILDREN,
    REINSERT_PIVOT_CELL_CHILDREN,
} from "../pivot/pivot_actions";
import { getListHighlights } from "../list/list_highlight_helpers";
const { topbarMenuRegistry } = registries;
const { HighlightStore } = stores;

//--------------------------------------------------------------------------
// Spreadsheet context menu items
//--------------------------------------------------------------------------

topbarMenuRegistry.addChild("new_sheet", ["file"], {
    name: _t("New"),
    sequence: 10,
    isVisible: (env) => env.newSpreadsheet,
    execute: (env) => env.newSpreadsheet(),
    icon: "o-spreadsheet-Icon.NEW",
});

topbarMenuRegistry.addChild("make_copy", ["file"], {
    name: _t("Make a copy"),
    sequence: 20,
    isVisible: (env) => env.makeCopy,
    execute: (env) => env.makeCopy(),
    separator: true,
    icon: "o-spreadsheet-Icon.COPY_FILE",
});

topbarMenuRegistry.addChild("download", ["file"], {
    name: _t("Download"),
    sequence: 40,
    isVisible: (env) => env.download,
    execute: (env) => env.download(),
    isReadonlyAllowed: true,
    icon: "o-spreadsheet-Icon.DOWNLOAD",
});

topbarMenuRegistry.addChild("download_as_json", ["file"], {
    name: _t("Download as JSON"),
    sequence: 50,
    isVisible: (env) => env.debug && env.downloadAsJson,
    execute: (env) => env.downloadAsJson(),
    isReadonlyAllowed: true,
    icon: "o-spreadsheet-Icon.DOWNLOAD_AS_JSON",
});

topbarMenuRegistry.addChild("print", ["file"], {
    name: _t("Print"),
    sequence: 60,
    separator: true,
    isVisible: (env) => env.print,
    execute: (env) => env.print(),
    icon: "o-spreadsheet-Icon.PRINT",
});

topbarMenuRegistry.addChild("save_as_template", ["file"], {
    name: _t("Save as template"),
    sequence: 70,
    isVisible: (env) => env.saveAsTemplate,
    execute: (env) => env.saveAsTemplate(),
    icon: "o-spreadsheet-Icon.SAVE",
});

topbarMenuRegistry.addChild("list_data_sources", ["data"], (env) => {
    const sequence = 53;
    const numberOfLists = env.model.getters.getListIds().length;
    return env.model.getters.getListIds().map((listId, index) => {
        const highlightProvider = {
            get highlights() {
                return getListHighlights(env.model.getters, listId);
            },
        };
        return {
            id: `item_list_${listId}`,
            name: env.model.getters.getListDisplayName(listId),
            sequence: sequence + index / numberOfLists,
            isReadonlyAllowed: true,
            execute: (env) => {
                env.openSidePanel("LIST_PROPERTIES_PANEL", { listId });
            },
            onStartHover: (env) => env.getStore(HighlightStore).register(highlightProvider),
            onStopHover: (env) => env.getStore(HighlightStore).unRegister(highlightProvider),
            icon: "o-spreadsheet-Icon.ODOO_LIST",
            separator: index === env.model.getters.getListIds().length - 1,
            secondaryIcon: (env) =>
                env.model.getters.isListUnused(listId)
                    ? "o-spreadsheet-Icon.UNUSED_LIST_WARNING"
                    : undefined,
            isVisible: (env) => !env.isSmall,
        };
    });
});

topbarMenuRegistry.addChild("chart_data_sources", ["data"], (env) => {
    const sequence = 56;
    const numberOfCharts = env.model.getters.getOdooChartIds().length;
    return env.model.getters.getOdooChartIds().map((chartId, index) => ({
        id: `item_chart_${chartId}`,
        name: env.model.getters.getOdooChartDisplayName(chartId),
        sequence: sequence + index / numberOfCharts,
        execute: (env) => {
            env.model.dispatch("SELECT_FIGURE", {
                figureId: env.model.getters.getFigureIdFromChartId(chartId),
            });
            env.openSidePanel("ChartPanel");
        },
        icon: "o-spreadsheet-Icon.INSERT_CHART",
        separator: index === env.model.getters.getOdooChartIds().length - 1,
        isVisible: (env) => !env.isSmall,
    }));
});

topbarMenuRegistry.addChild("refresh_data_sources", ["data"], {
    id: "refresh_all_data",
    name: _t("Refresh all data"),
    sequence: 58,
    execute: (env) => {
        env.model.dispatch("REFRESH_ALL_DATA_SOURCES");
    },
    separator: true,
    icon: "o-spreadsheet-Icon.REFRESH_DATA",
});

const reinsertDynamicPivotMenu = {
    id: "reinsert_dynamic_pivot",
    name: _t("Re-insert dynamic pivot"),
    sequence: 60,
    children: [REINSERT_DYNAMIC_PIVOT_CHILDREN],
    isVisible: (env) =>
        env.model.getters.getPivotIds().some((id) => env.model.getters.getPivot(id).isValid()),
    icon: "o-spreadsheet-Icon.INSERT_PIVOT",
};
const reinsertStaticPivotMenu = {
    id: "reinsert_static_pivot",
    name: _t("Re-insert static pivot"),
    sequence: 70,
    children: [REINSERT_STATIC_PIVOT_CHILDREN],
    isVisible: (env) =>
        env.model.getters.getPivotIds().some((id) => env.model.getters.getPivot(id).isValid()),
    icon: "o-spreadsheet-Icon.INSERT_PIVOT",
};

const reinsertPivotCell = {
    id: "reinsert_pivot_cell",
    name: _t("Re-insert pivot cell"),
    sequence: 72,
    children: [REINSERT_PIVOT_CELL_CHILDREN],
    isVisible: (env) =>
        env.model.getters.getPivotIds().some((id) => env.model.getters.getPivot(id).isValid()),
    icon: "o-spreadsheet-Icon.INSERT_PIVOT",
};

const reInsertListMenu = {
    id: "reinsert_list",
    name: _t("Re-insert list"),
    sequence: 74,
    children: [REINSERT_LIST_CHILDREN],
    isVisible: (env) =>
        env.model.getters
            .getListIds()
            .some((id) => env.model.getters.getListDataSource(id).isModelValid()),
    icon: "o-spreadsheet-Icon.INSERT_LIST",
};

const insertPivotMenu = {
    name: _t("Pivot table"),
    sequence: 52,
    children: [
        {
            id: "insert_pivot_from_range",
            name: _t("From range"),
            sequence: 1,
            execute: (env) => {
                const pivotId = env.model.uuidGenerator.smallUuid();
                const newSheetId = env.model.uuidGenerator.smallUuid();
                const result = env.model.dispatch("INSERT_NEW_PIVOT", { pivotId, newSheetId });
                if (result.isSuccessful) {
                    env.openSidePanel("PivotSidePanel", { pivotId });
                }
            },
        },
        {
            id: "insert_pivot_from_odoo_model",
            name: _t("From Odoo data"),
            sequence: 2,
            execute: (env) => {
                env.openSidePanel("NewOdooPivotSidePanel");
            },
        },
    ],
    icon: "o-spreadsheet-Icon.PIVOT",
    isVisible: (env) => !env.isSmall,
};

topbarMenuRegistry.addChild("reinsert_list", ["data"], reInsertListMenu);
topbarMenuRegistry.replaceChild("reinsert_dynamic_pivot", ["data"], reinsertDynamicPivotMenu);
topbarMenuRegistry.replaceChild("reinsert_static_pivot", ["data"], reinsertStaticPivotMenu);
topbarMenuRegistry.replaceChild("insert_pivot", ["insert"], insertPivotMenu);
topbarMenuRegistry.addChild("reinsert_pivot_cell", ["data"], reinsertPivotCell);
