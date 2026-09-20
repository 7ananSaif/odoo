import * as spreadsheet from "@odoo/o-spreadsheet";
import { initCallbackRegistry } from "@spreadsheet/o_spreadsheet/init_callbacks";

import { PivotAutofillPlugin } from "./plugins/pivot_autofill_plugin";
import { PivotDetailsSidePanel } from "./side_panels/pivot_details_side_panel";

import "./autofill";
import { insertPivot } from "./pivot_init_callback";
import { NewPivotSidePanel } from "./side_panels/new_pivot_side_panel/new_pivot_side_panel";
import { _t } from "@web/core/l10n/translation";
import { PivotOdooInsertion } from "./plugins/pivot_odoo_insertion";

const { featurePluginRegistry, pivotSidePanelRegistry, sidePanelRegistry } = spreadsheet.registries;

featurePluginRegistry.add("odooPivotAutofillPlugin", PivotAutofillPlugin);
featurePluginRegistry.add("odooPivotOdooInsertionPlugin", PivotOdooInsertion);

pivotSidePanelRegistry.add("ODOO", {
    editor: PivotDetailsSidePanel,
});

initCallbackRegistry.add("insertPivot", insertPivot);

sidePanelRegistry.add("NewOdooPivotSidePanel", {
    title: _t("New Odoo Pivot"),
    Body: NewPivotSidePanel,
});
