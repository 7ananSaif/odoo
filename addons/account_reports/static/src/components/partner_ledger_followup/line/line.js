import { AccountReport } from "@account_reports/components/account_report/account_report";
import { AccountReportLine } from "@account_reports/components/account_report/line/line";
import { PartnerLedgerFollowupLineCell } from "@account_reports/components/partner_ledger_followup/line_cell/line_cell";

export class PartnerLedgerFollowupLine extends AccountReportLine {
    static template = "account_reports.PartnerLedgerFollowupLine";
    static components = {
        ...AccountReportLine.components,
        PartnerLedgerFollowupLineCell,
    };
}
AccountReport.registerCustomComponent(PartnerLedgerFollowupLine);
