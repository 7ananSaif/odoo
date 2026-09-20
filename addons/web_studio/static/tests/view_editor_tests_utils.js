import { getFixture } from "@odoo/hoot";
import { waitFor } from "@odoo/hoot-dom";
import { Component, useSubEnv, xml } from "@odoo/owl";

import {
    contains,
    getMockEnv,
    makeMockEnv,
    MockServer,
    mountWithCleanup,
    onRpc,
    parseViewProps,
    registerInlineViewArchs,
} from "@web/../tests/web_test_helpers";
import { useOwnDebugContext } from "@web/core/debug/debug_context";

import { MainComponentsContainer } from "@web/core/main_components_container";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { getDefaultConfig } from "@web/views/view";
import { EditionFlow } from "@web_studio/client_action/editor/edition_flow";
import { ViewEditor } from "@web_studio/client_action/view_editor/view_editor";
import { useStudioServiceAsReactive } from "@web_studio/studio_service";

const serviceRegistry = registry.category("services");

class ViewEditorHoc extends Component {
    static template = xml`<ViewEditor action="{}" className="''" />`;
    static components = { ViewEditor };
    static props = ["*"];
    setup() {
        const editionFlow = new EditionFlow(this.env, {
            dialog: useService("dialog"),
            studio: useStudioServiceAsReactive(),
            view: useService("view"),
        });
        useSubEnv({
            editionFlow,
        });
        if (this.env.debug) {
            useOwnDebugContext();
        }
    }
}

class ViewEditorParent extends Component {
    static components = { ViewEditorHoc, MainComponentsContainer };
    static props = {};
    static template = xml`
        <MainComponentsContainer />
        <div class="o_studio h-100">
            <div class="o_web_studio_editor">
                <div class="o_action_manager">
                    <div class="o_web_studio_editor_manager d-flex flex-row w-100 h-100">
                        <ViewEditorHoc />
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * @param {Request | { model: string, view_id: number | false }} params
 * @param {string} viewType
 * @param {string} arch
 */
export async function editView(params, viewType, arch) {
    if (params instanceof Request) {
        ({ params } = await params.json());
    }
    const { model: modelName, view_id: viewId } = params;
    const model = MockServer.env[modelName];
    registerInlineViewArchs(modelName, {
        [[viewType, viewId]]: arch,
    });
    const result = model.get_views([[viewId || false, viewType]]);
    result.models[modelName].fields = model.fields_get(); // return all fields
    return result;
}

export function disableHookAnimation() {
    const fixture = getFixture();
    fixture.querySelectorAll(".o_web_studio_hook, .o_web_studio_hook_separator").forEach((sep) => {
        sep.style.setProperty("transition", "none", "important");
        sep.style.setProperty("min-height", "20px");
    });
}

export function handleDefaultStudioRoutes() {
    onRpc("ir.model", "studio_model_infos", () => ({
        is_mail_thread: false,
        is_mail_activity: false,
        state: "base",
        record_ids: [1],
    }));
    onRpc("/web_studio/edit_view", () => {});
    onRpc("/web_studio/edit_view_arch", () => {});
    onRpc("/web_studio/get_actions_for_model", () => []);
    onRpc("/web_studio/get_default_value", () => ({ default_value: undefined }));
    onRpc("/web_studio/get_studio_view_arch", () => ({ studio_view_arch: "" }));
    onRpc("get_approval_spec", ({ args }) => {
        const result = { all_rules: {} };
        const args_list = args[0];
        for (const { model } of args_list) {
            result[model] = [];
        }
        return result;
    });
}

export async function mountViewEditor(params) {
    const actionToEdit = { res_model: params.resModel };
    const config = { ...getDefaultConfig(), ...params.config };
    params.viewId = params.viewId || 99999999;

    prepareRegistry(params.filterRegistry ?? true);
    const env = params.env || getMockEnv() || (await makeMockEnv({ config }));

    params = parseViewProps(params);
    actionToEdit.views = [[params.viewId, params.type]];

    handleDefaultStudioRoutes();
    env.services.studio.setParams({
        viewType: params.type,
        editorTab: "views",
        action: actionToEdit,
        controllerState: {
            resId: params.resId,
        },
        mode: "editor",
    });
    return mountWithCleanup(ViewEditorParent, {
        env,
    });
}

function prepareRegistry(filterRegistry) {
    registry.category("main_components").remove("mail.ChatHub");
    registry.category("main_components").remove("discuss.CallInvitations");
    registry.category("main_components").remove("bus.ConnectionAlert");
    serviceRegistry.add("messaging", makeFakeMessagingService());
    if (!filterRegistry) {
        return;
    }
    const REQUIRED_SERVICES = [
        "mail.popout",
        "title",
        "orm",
        "field",
        "name",
        "tree_processor",
        "http",
        "home_menu",
        "menu",
        "action",
        "studio",
        "notification",
        "dialog",
        "popover",
        "hotkey",
        "localization",
        "company",
        "view",
        "overlay",
        "ui",
        "effect",
        "web_studio.get_approval_spec_batched",
    ];
    Object.keys(serviceRegistry.content).forEach((e) => {
        if (!REQUIRED_SERVICES.includes(e)) {
            serviceRegistry.remove(e);
        }
    });
}

function makeFakeMessagingService() {
    const chatter = {
        update: () => {},
        refresh: () => {},
        exists: () => {},
        delete: () => {},
        thread: {},
    };

    const messaging = {
        models: {
            Chatter: {
                insert: () => chatter,
            },
        },
    };

    const service = {
        get: () => messaging,
        modelManager: {
            messaging,
            messagingCreatedPromise: new Promise((resolve) => resolve()),
            startListening: () => {},
            stopListening: () => {},
            removeListener: () => {},
        },
    };

    return {
        start(env) {
            return service;
        },
    };
}

export async function openStudio(params = {}) {
    await contains(".o_main_navbar .o_web_studio_navbar_item button").click();
    if (params.noEdit) {
        await contains(".o_menu_sections a").click();
        await waitFor(".o_web_studio_views");
    }
    if (params.report) {
        await contains(".o_menu_sections a:eq(1)").click();
        await contains(`.o_kanban_record [data-id="${params.report}"`).click();
        await waitFor(".o_web_studio_report_editor_manager");
    }
}
