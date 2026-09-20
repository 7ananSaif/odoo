import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { Notebook } from "@web/core/notebook/notebook";

import { Component, onWillStart, useState } from "@odoo/owl";
import { SpreadsheetSelectorPanel } from "./spreadsheet_selector_panel";

const NAME_LABELS = {
    PIVOT: _t("Pivot name"),
    LIST: _t("List name"),
    LINK: _t("Link name"),
    GRAPH: _t("Graph name"),
};

/**
 * @typedef State
 * @property {Object} spreadsheets
 * @property {string} panel
 * @property {string} name
 * @property {number|null} selectedSpreadsheetId
 * @property {string} [threshold]
 * @property {Object} pagerProps
 * @property {number} pagerProps.offset
 * @property {number} pagerProps.limit
 * @property {number} pagerProps.total
 */

export class SpreadsheetSelectorDialog extends Component {
    static template = "spreadsheet_edition.SpreadsheetSelectorDialog";
    static components = { Dialog, Notebook };
    static props = {
        actionOptions: Object,
        type: String,
        threshold: { type: Number, optional: true },
        maxThreshold: { type: Number, optional: true },
        name: String,
        close: Function,
    };

    setup() {
        /** @type {State} */
        this.state = useState({
            threshold: this.props.threshold,
            name: this.props.name,
            confirmationIsPending: false,
        });
        this.actionState = {
            getOpenSpreadsheetAction: () => {},
        };
        this.notification = useService("notification");
        this.actionService = useService("action");
        const orm = useService("orm");
        onWillStart(async () => {
            const spreadsheetModels = await orm.call(
                "spreadsheet.mixin",
                "get_selector_spreadsheet_models"
            );
            this.noteBookPages = spreadsheetModels.map(({ model, display_name, allow_create }) => ({
                Component: SpreadsheetSelectorPanel,
                id: model,
                title: display_name,
                props: {
                    model,
                    displayBlank: allow_create,
                    onSpreadsheetSelected: this.onSpreadsheetSelected.bind(this),
                    onSpreadsheetDblClicked: this._onInsert.bind(this),
                },
            }));
        });
    }

    get nameLabel() {
        return NAME_LABELS[this.props.type];
    }

    get title() {
        return _t("Insert in Spreadsheet");
    }

    /**
     * @param {number|null} id
     */
    onSpreadsheetSelected({ getOpenSpreadsheetAction }) {
        this.actionState = {
            getOpenSpreadsheetAction,
        };
    }

    async _onInsert() {
        if (this.state.confirmationIsPending) {
            return;
        }
        this.state.confirmationIsPending = true;
        const action = await this.actionState.getOpenSpreadsheetAction();
        if (!action) {
            this.state.confirmationIsPending = false;
            return;
        }
        const threshold = this.state.threshold ? parseInt(this.state.threshold, 10) : 0;
        const name = this.state.name.toString();

        // the action can be preceded by a notification
        const actionOpen = action;
        actionOpen.params = this._addToPreprocessingAction(actionOpen.params, threshold, name);
        this.actionService.doAction(action);
        this.props.close();
    }

    _addToPreprocessingAction(actionParams, threshold, name) {
        return {
            ...this.props.actionOptions,
            preProcessingAsyncActionData: {
                ...this.props.actionOptions.preProcessingAsyncActionData,
                threshold,
                name,
            },
            preProcessingActionData: {
                ...this.props.actionOptions.preProcessingActionData,
                threshold,
                name,
            },
            ...actionParams,
        };
    }

    _onDiscard() {
        this.props.close();
    }
}
