import { mailModels } from "@mail/../tests/mail_test_helpers";
import { mailDataHelpers } from "@mail/../tests/mock_server/mail_mock_server";

import { fields, makeKwArgs } from "@web/../tests/web_test_helpers";
import { serializeDateTime } from "@web/core/l10n/dates";

const { DateTime } = luxon;

export class DiscussChannel extends mailModels.DiscussChannel {
    whatsapp_channel_valid_until = fields.Datetime({
        default: () => serializeDateTime(DateTime.local().plus({ days: 1 })),
    });
    wa_account_id = fields.Generic({ default: () => 1 });

    /**
     * @override
     * @type {typeof mailModels.DiscussChannel["prototype"]["_to_store"]}
     */
    _to_store(store, fields) {
        /** @type {import("mock_models").ResPartner} */
        const ResPartner = this.env["res.partner"];

        super._to_store(...arguments);
        if (fields && Array.isArray(fields) && fields.length) {
            return;
        }
        const channels = this._filter([
            ["id", "in", this.map((channel) => channel.id)],
            ["channel_type", "=", "whatsapp"],
        ]);
        for (const channel of channels) {
            store._add_record_fields(this.browse(channel.id), {
                whatsapp_channel_valid_until: channel.whatsapp_channel_valid_until || false,
                whatsapp_partner_id: mailDataHelpers.Store.one(
                    ResPartner.browse(channel.whatsapp_partner_id),
                    makeKwArgs({ only_id: true })
                ),
                wa_account_id: mailDataHelpers.Store.one(
                    this.env["whatsapp.account"].browse(channel.wa_account_id),
                    makeKwArgs({ fields: ["name"] })
                ),
            });
        }
    }

    /**
     * @override
     * @type {typeof mailModels.DiscussChannel["prototype"]["_types_allowing_seen_infos"]}
     */
    _types_allowing_seen_infos() {
        return super._types_allowing_seen_infos(...arguments).concat(["whatsapp"]);
    }
}
