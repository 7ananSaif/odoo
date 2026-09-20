import { Thread } from "@mail/core/common/thread";
import { AccountReportMessage } from "./message";

export class AccountReportThread extends Thread {
    static template = "account_reports.Thread";
    static props = [...Thread.props, "reportController?"];
    static components = { ...Thread.components, Message: AccountReportMessage };
}
