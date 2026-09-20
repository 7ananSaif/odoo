import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";

export async function downloadDocumentAndReturn(env, action) {
    const url = action.params.url;
    const res_model = action.params?.res_model;
    const res_id = action.params?.res_id;
    const view_mode = action.params?.view_mode;
    const redirect_to = action.params?.redirect_to;
    try {
        browser.open(url, '_blank');
    }
    finally {
        if (redirect_to) {
            return redirect_to;
        }
        else {
            return {
                type: "ir.actions.act_window",
                res_model: res_model,
                res_id: res_id,
                views: [[false, view_mode]],
                view_mode: view_mode,
                target: 'main',
            };
        }
    }
}

registry.category("actions").add("sign_download_document_and_return", downloadDocumentAndReturn);
