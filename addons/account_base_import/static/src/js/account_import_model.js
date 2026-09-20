import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { BaseImportModel } from "@base_import/import_model";

class AccountMoveLineImportModel extends BaseImportModel {
    get importOptions() {
        const options = super.importOptions;
        if (this.resModel === "account.move.line") {
            Object.assign(options.name_create_enabled_fields, {
                journal_id: true,
                account_id: true,
                partner_id: true,
            });
        }
        return options;
    }
}

/**
 * @returns {AccountMoveLineImportModel}
 */
export function useAccountMoveLineImportModel({ env, context }) {
    const orm = useService("orm");
    return useState(new AccountMoveLineImportModel({ env, context, orm }));
}
