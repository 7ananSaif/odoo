import { Chatter } from "@mail/chatter/web_portal/chatter";
import { AccountReportComposer } from "./composer";
import { AccountReportThread } from "./thread";

export class AccountReportChatter extends Chatter {
    static template = "account_reports.Chatter";
    static props = [...Chatter.props, "reportController?", "date_to", "list?"];
    static components = {
        ...Chatter.components,
        Composer: AccountReportComposer,
        Thread: AccountReportThread,
    };
}
