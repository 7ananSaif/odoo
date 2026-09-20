import { Message } from "@mail/core/common/message";

export class AccountReportMessage extends Message {
    static props = [...Message.props, "reportController?"];
}
