import { models, defineModels } from "@web/../tests/web_test_helpers";
import { mailModels } from "@mail/../tests/mail_test_helpers";

export class SignDocument extends models.ServerModel {
    _name = "sign.document";

    _records = [
        {
            id: 1,
            template_id: 1,
        },
    ];
}

export class SignTemplate extends models.ServerModel {
    _name = "sign.template";

    _records = [
        {
            id: 1,
            display_name: "yop.pdf",
            document_ids: [1],
            tag_ids: [1, 2],
            color: 1,
            active: true,
        },
    ];
}

export class SignTemplateTag extends models.ServerModel {
    _name = "sign.template.tag";

    _records = [
        {
            id: 1,
            name: "New",
            color: 1,
        },
        {
            id: 2,
            name: "Draft",
            color: 2,
        },
    ];
}

export class SignItemRole extends models.ServerModel {
    _name = "sign.item.role";

    _records = [
        {
            id: 1,
            name: "Customer",
        },
        {
            id: 2,
            name: "Company",
        },
    ];
}

export class SignSendRequestSigner extends models.ServerModel {
    _name = "sign.send.request.signer";

    _records = [
        {
            id: 1,
            partner_id: false,
            role_id: 1,
            mail_sent_order: 1,
        },
        {
            id: 2,
            partner_id: false,
            role_id: 2,
            mail_sent_order: 1,
        },
    ];
}

export class SignSendRequest extends models.ServerModel {
    _name = "sign.send.request";

    _records = [
        {
            id: 1,
            signer_ids: [1, 2],
            set_sign_order: false,
        },
        {
            id: 2,
            signer_ids: [2],
            set_sign_order: false,
        },
    ];
}

export const signModels = {
    ...mailModels,
    SignDocument,
    SignTemplate,
    SignTemplateTag,
    SignSendRequestSigner,
    SignSendRequest,
    SignItemRole,
};

export function defineSignModels() {
    return defineModels(signModels);
}
