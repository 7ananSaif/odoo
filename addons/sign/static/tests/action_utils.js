import {
    onRpc,
    patchWithCleanup,
    defineActions,
    mountWebClient,
} from "@web/../tests/web_test_helpers";
import { Document } from "@sign/components/sign_request/document_signable";

export const actionId = 9;
export const defaultMockRPC = () =>
    Promise.resolve({
        html: `
        <span>
            def
            <div class='o_sign_cp_pager'>
                <div class="signer-status">
                    <p class="o_sign_signer_status o_sign_signer_waiting" data-id="1"></p>
                    <p class="o_sign_signer_status o_sign_signer_waiting" data-id="2"></p>
                </div>
                <input id="o_sign_input_sign_request_state" type="hidden" value="sent"/>
            </div>
            <iframe srcdoc="<body></body>" src="/sign/get_document/5/abc" class="o_iframe o_sign_pdf_iframe"/>
        </span>
        `,
        context: {},
    });

export const defaultGetOriginalDocuments = () =>
    Promise.resolve({
        original_documents: [{
            id: 1,
            name: "test.pdf"
        }]
    });

export const defaultGetCompletedDocuments = () =>
    Promise.resolve({
        completed_documents: [{
            id: 1,
            name: "test.pdf"
        }]
    });

export async function createDocumentWebClient(config) {
    config = {
        actionContext: config.actionContext || {},
        getDataFromHTML: config.getDataFromHTML || (() => {}),
        tag: config.tag,
    };

    const actions = {
        id: actionId,
        name: "A Client Action",
        tag: config.tag,
        type: "ir.actions.client",
        context: {
            id: 5,
            token: "abc",
            state: "sent",
            create_uid: 1,
            request_item_states: { 1: true, 2: false },
            ...config.actionContext,
        },
    };

    patchWithCleanup(Document.prototype, {
        getDataFromHTML() {
            config.getDataFromHTML();
            this.requestState = "sent";
        },
        initializeIframe() {
            return;
        },
    });

    onRpc("/sign/get_document/5/abc", defaultMockRPC);
    onRpc("/sign/get_original_documents/5/abc", defaultGetOriginalDocuments);
    onRpc("/sign/get_completed_documents/5/abc", defaultGetCompletedDocuments);
    defineActions([actions]);
    await mountWebClient();
}
