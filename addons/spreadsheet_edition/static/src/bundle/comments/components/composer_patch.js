import { patch } from "@web/core/utils/patch";
import { Composer } from "@mail/core/common/composer";

patch(Composer.prototype, {
    get allowUpload() {
        return this._isSpreadsheetCellThread() ? false : super.allowUpload;
    },

    /**
     * Utility to check if the current thread is a spreadsheet cell thread.
     * @private
     */
    _isSpreadsheetCellThread() {
        const threadModel = (this.thread ?? this.message?.thread)?.model;
        return threadModel === "spreadsheet.cell.thread";
    },
});
