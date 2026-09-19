import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { Model, registries } from "@odoo/o-spreadsheet";
import { UNTITLED_SPREADSHEET_NAME } from "@spreadsheet/helpers/constants";
import { AbstractSpreadsheetAction } from "@spreadsheet_edition/bundle/actions/abstract_spreadsheet_action";
import { _t } from "@web/core/l10n/translation";

import { useState, useSubEnv } from "@odoo/owl";
const { topbarMenuRegistry } = registries;

export class SpreadsheetAction extends AbstractSpreadsheetAction {
    static template = "documents_spreadsheet.SpreadsheetAction";
    static path = "spreadsheet";
    static displayName = _t("Spreadsheet");

    resModel = "documents.document";
    threadField = "document_id";

    setup() {
        super.setup();
        this.state = useState({
            isFavorited: false,
            spreadsheetName: UNTITLED_SPREADSHEET_NAME,
        });
        this.threadId = this.params?.thread_id;
        this.notification = useService("notification");
        this.dialogService = useService("dialog");
        this.documentService = useService("document.document");
        useSubEnv({
            newSpreadsheet: this.createNewSpreadsheet.bind(this),
            makeCopy: this.makeCopy.bind(this),
            saveAsTemplate: this.saveAsTemplate.bind(this),
            onShareSpreadsheet: this.shareSpreadsheet.bind(this),
            onFreezeAndShareSpreadsheet: this.freezeAndShareSpreadsheet.bind(this),
            moveToTrash: this.moveToTrash.bind(this),
            isFrozenSpreadsheet: () => this.data.handler === "frozen_spreadsheet",
            isArchived: () => Boolean(this.data?.is_archived),
        });
    }

    /**
     * @override
     */
    _initializeWith(data) {
        super._initializeWith(data);
        this.state.isFavorited = data.is_favorited;
    }

    /**
     * @param {OdooEvent} ev
     * @returns {Promise}
     */
    async _onSpreadSheetFavoriteToggled(ev) {
        this.state.isFavorited = !this.state.isFavorited;
        return await this.orm.call("documents.document", "toggle_favorited", [[this.resId]]);
    }

    /**
     * Create a new sheet and display it
     */
    async createNewSpreadsheet() {
        const action = await this.orm.call("documents.document", "action_open_new_spreadsheet");
        this.actionService.doAction(action, { clear_breadcrumbs: true });
    }

    onSpreadsheetLeftUpdateVals() {
        return {
            ...super.onSpreadsheetLeftUpdateVals(),
            is_multipage: this.model.getters.getSheetIds().length > 1,
        };
    }

    /**
     * @private
     * @returns {Promise}
     */
    async saveAsTemplate() {
        const model = new Model(this.model.exportData(), {
            custom: {
                env: this.env,
                odooDataProvider: this.model.config.custom.odooDataProvider,
            },
        });
        const data = model.exportData();
        const name = this.state.spreadsheetName;

        this.actionService.doAction("documents_spreadsheet.save_spreadsheet_template_action", {
            additionalContext: {
                default_template_name: _t("%s - Template", name),
                default_spreadsheet_data: JSON.stringify(data),
                default_thumbnail: this.getThumbnail(),
            },
        });
    }

    /**
     * @returns <string> the url to share the spreadsheet
     */
    shareSpreadsheet() {
        this.documentService.openSharingDialog([this.resId]);
    }

    async freezeAndShareSpreadsheet() {
        if (this.data.handler === "frozen_spreadsheet") {
            this.notification.add(_t("You can not freeze a frozen spreadsheet"));
            return;
        }

        const { freezeOdooData } = odoo.loader.modules.get("@spreadsheet/helpers/model");
        const data = await freezeOdooData(this.model);

        const record = await this.orm.call("documents.document", "action_freeze_and_copy", [
            this.resId,
            JSON.stringify(data),
            this.model.exportXLSX().files,
        ]);
        this.documentService.openSharingDialog([record.id]);
    }

    async moveToTrash() {
        const wasArchived = await this.documentService.moveToTrash([this.resId]);
        if (!wasArchived) {
            return;
        }
        if (this.env.config.breadcrumbs.length > 1) {
            await this.actionService.restore();
        } else {
            await this.actionService.doAction("documents.document_action");
        }
        this.notification.add(_t("Spreadsheet moved to trash"), { type: "success" });
    }
}

registry.category("actions").add("action_open_spreadsheet", SpreadsheetAction, { force: true });

topbarMenuRegistry.addChild("move_to_trash", ["file"], {
    name: _t("Move to trash"),
    sequence: 80,
    isVisible: (env) => env.moveToTrash,
    execute: (env) => env.moveToTrash(),
    icon: "o-spreadsheet-Icon.TRASH_FILLED",
});
