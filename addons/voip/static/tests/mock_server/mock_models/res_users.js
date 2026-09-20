import { mailModels } from "@mail/../tests/mail_test_helpers";
import { fields, makeKwArgs } from "@web/../tests/web_test_helpers";

export class ResUsers extends mailModels.ResUsers {
    voip_provider_id = fields.Many2one({
        relation: "voip.provider",
        default() {
            return this.env["voip.provider"][0].id;
        },
    });

    /** @override */
    _init_store_data(store) {
        const VoipCall = this.env["voip.call"];
        const VoipProvider = this.env["voip.provider"];
        /** @type {import("mock_models").ResUsers} */
        const ResUsers = this.env["res.users"];

        super._init_store_data(...arguments);
        const [user] = ResUsers.search_read([["id", "=", this.env.uid]]);
        if (user) {
            const [provider] = VoipProvider.search_read([["id", "=", user.voip_provider_id[0]]]);
            store.add({
                voipConfig: {
                    missedCalls: VoipCall._get_number_of_missed_calls(),
                    mode: provider.mode,
                    pbxAddress: provider.pbx_ip || "localhost",
                    recordingPolicy: provider.recording_policy || "disabled",
                    webSocketUrl: provider.ws_server || "ws://localhost",
                },
            });
        }
    }

    reset_last_seen_phone_call() {
        const domain = [("user_id", "=", [this.env.user.id])];
        const last_call = this.env["voip.call"].search(
            domain,
            makeKwArgs({
                limit: 1,
                order: "id DESC",
            })
        );
        this.env.user.last_seen_phone_call = last_call.id;
    }
}
