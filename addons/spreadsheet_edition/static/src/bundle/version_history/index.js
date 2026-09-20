import { registries } from "@odoo/o-spreadsheet";
import { _t } from "@web/core/l10n/translation";

registries.topbarMenuRegistry.addChild("version_history", ["file"], {
    name: _t("See version history"),
    sequence: 90,
    isVisible: (env) => env.showHistory,
    execute: (env) => env.showHistory(),
    icon: "o-spreadsheet-Icon.VERSION_HISTORY",
});

registries.topbarMenuRegistry.addChild("clear_history", ["file"], {
    name: _t("Snapshot"),
    sequence: 100,
    separator: true,
    isVisible: (env) => env.debug,
    execute: (env) => {
        env.model.session.snapshot(env.model.exportData());
        env.model.garbageCollectExternalResources();
        window.location.reload();
    },
    icon: "o-spreadsheet-Icon.CAMERA",
});
