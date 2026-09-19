import { mailModels } from "@mail/../tests/mail_test_helpers";
import { mailDataHelpers } from "@mail/../tests/mock_server/mail_mock_server";

export class ResPartner extends mailModels.ResPartner {
    /** @override */
    _compute_display_name() {
        super._compute_display_name();
        for (const record of this) {
            if (record.company_name) {
                record.display_name = `${record.company_name}, ${record.display_name}`;
            }
        }
    }

    get_contacts() {
        const store = new mailDataHelpers.Store();
        const contacts = this.browse(this.search([["phone", "!=", false]]));
        return store.add(contacts, this._voip_get_store_fields()).get_result();
    }

    /** @param {number[]} ids */
    _format_contacts(ids) {
        const contacts = this.browse(ids);
        return contacts.map((contact) => ({
            id: contact.id,
            email: contact.email,
            phone: contact.phone,
            name: contact.display_name,
            t9_name: contact.t9_name,
        }));
    }

    _voip_get_store_fields() {
        return ["id", "email", "phone", "name", "t9_name"];
    }
}
