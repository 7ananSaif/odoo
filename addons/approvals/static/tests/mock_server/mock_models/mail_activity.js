import { mailModels } from "@mail/../tests/mail_test_helpers";

export class MailActivity extends mailModels.MailActivity {
    /** @param {number[]} ids */
    _to_store(store) {
        super._to_store(...arguments);
        for (const activity of this._filter([
            ["id", "in", this.map((activity) => activity.id)],
            ["res_model", "=", "approval.request"],
        ])) {
            // check on activity type being approval not done here for simplicity
            const [approver_id] = this.env["approval.approver"]._filter([
                ["request_id", "=", activity.res_id],
                ["user_id", "=", activity.user_id],
            ]);
            if (approver_id) {
                store._add_record_fields(this.browse(activity.id), {
                    approver_id: { id: approver_id.id, status: approver_id.status },
                });
            }
        }
    }
}
