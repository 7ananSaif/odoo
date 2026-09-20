import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { useAutofocus } from "@web/core/utils/hooks";

const DEFAULT_LIMIT = 9;

export class SpreadsheetSelectorGrid extends Component {
    static template = "spreadsheet_edition.SpreadsheetSelectorGrid";
    static defaultProps = {
        displayBlank: true,
    };

    static props = {
        spreadsheets: Array,
        onSpreadsheetSelected: Function,
        onSpreadsheetDblClicked: Function,
        getThumbnailURL: Function,
        selectedSpreadsheetId: Number | null,
        displayBlank: { type: Boolean, optional: true },
        blankCardLabel: { type: String, optional: true },
    };

    blankThumbnailPlaceholder = "/spreadsheet/static/img/spreadsheet.svg";

    setup() {
        useAutofocus();
        useHotkey("ArrowRight", () => this._onArrowKey("right"), {
            allowRepeat: true,
        });
        useHotkey("ArrowLeft", () => this._onArrowKey("left"), {
            allowRepeat: true,
        });
    }

    get blankTemplate() {
        return {
            id: null,
            display_name: this.props.blankCardLabel ?? _t("Blank spreadsheet"),
            thumbnail: "/spreadsheet/static/img/spreadsheet.svg",
        };
    }

    /**
     * @returns {Array} - The list of spreadsheets to display in the grid.
     */
    get spreadsheets() {
        if (!this.props.displayBlank) {
            return this.props.spreadsheets;
        }
        return [this.blankTemplate, ...this.props.spreadsheets];
    }

    /**
     * @returns {Number} - The number of spreadsheets to display per page.
     */
    get itemsPerPage() {
        return this.props.displayBlank ? DEFAULT_LIMIT : DEFAULT_LIMIT + 1;
    }

    /**
     * Handles the arrow key press event to navigate through spreadsheets and pages.
     * @param {left|right} direction - The direction of the arrow key.
     */
    async _onArrowKey(direction) {
        const index = this.spreadsheets.findIndex(
            (spreadsheet) => spreadsheet.id === this.props.selectedSpreadsheetId
        );

        // Navigate to the next or previous spreadsheet
        const navigateToSpreadsheet = (newSpreadsheetId) => {
            if (newSpreadsheetId === this.props.selectedSpreadsheetId) {
                return;
            }
            this.props.onSpreadsheetSelected(newSpreadsheetId);
        };

        switch (direction) {
            case "left":
                if (index > 0 && index < this.spreadsheets.length) {
                    // Navigate to the previous spreadsheet
                    navigateToSpreadsheet(this.spreadsheets[index - 1].id);
                }
                break;
            case "right":
                if (index < this.spreadsheets.length - 1) {
                    // Navigate to the next spreadsheet
                    navigateToSpreadsheet(this.spreadsheets[index + 1].id);
                }
                break;
            default:
                break;
        }
    }
}
