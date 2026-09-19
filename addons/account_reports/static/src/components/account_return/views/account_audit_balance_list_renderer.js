import { useService } from "@web/core/utils/hooks";

import { ListRenderer } from "@web/views/list/list_renderer";
import { AccountReportChatter } from "@account_reports/components/mail/chatter";
import { useAuditBalanceListChatterService } from "./account_audit_balance_list_chatter_service";
import { useEffect, useRef } from "@odoo/owl";

export class AccountAuditBalanceListRenderer extends ListRenderer {
    static template = "account_reports.account_audit_balance_list_renderer";

    static components = {
        ...ListRenderer.components,
        AccountReportChatter,
    };

    setup() {
        super.setup();
        this.ui = useService("ui");
        this.chatterService = useAuditBalanceListChatterService();

        this.chatterRef = useRef("AuditChatter");

        useEffect(() => {
            if (this.props.list.editedRecord) {
                this.chatterService.openChatter(this.props.list.editedRecord.evalContext.id);
            } else {
                this.chatterService.closeChatter();
            }
        }, () => [this.props.list.editedRecord]);
    }

    onGlobalClick(event) {
        if (this.chatterRef.el.contains(event.target)) {
            // ignore clicks inside the chatter as we dont want it to close when clicking inside it
            return;
        }
        super.onGlobalClick(event);
    }

    getCellClass(column, record) {
        const classNames = super.getCellClass(column, record);
        if (column.name === 'audit_balance' && record.data.audit_balance_show_warning
            || column.name === 'audit_previous_balance' && record.data.audit_previous_balance_show_warning) {
            return `${classNames} table-warning`;
        }
        return classNames;
    }
}
