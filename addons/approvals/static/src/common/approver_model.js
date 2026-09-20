import { Record } from "@mail/core/common/record";

export class ApprovalApprover extends Record {
    static _name = "approval.approver";
    static id = "id";
    /** @type {number} */
    id;
    /** @type {"new"|"pending"|"waiting"|"approved"|"refused"|"cancel"} */
    status;
}

ApprovalApprover.register();
