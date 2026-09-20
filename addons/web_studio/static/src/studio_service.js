import { registry } from "@web/core/registry";
import { resetViewCompilerCache } from "@web/views/view_compiler";
import { _t } from "@web/core/l10n/translation";

import { EventBus, onWillUnmount, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { router, routerBus } from "@web/core/browser/router";
import { Cache } from "@web/core/utils/cache";
import { user } from "@web/core/user";
import { rpcBus } from "@web/core/network/rpc";

const URL_VIEW_KEY = "_view_type";
const URL_TAB_KEY = "_tab";
const URL_MODE_KEY = "mode";
const URL_REPORT_ID_KEY = "_report_id";

export const MODES = {
    EDITOR: "editor",
    HOME_MENU: "home_menu",
    APP_CREATOR: "app_creator",
};

export class NotEditableActionError extends Error {}

const SUPPORTED_VIEW_TYPES = {
    activity: _t("Activity"),
    calendar: _t("Calendar"),
    cohort: _t("Cohort"),
    form: _t("Form"),
    gantt: _t("Gantt"),
    graph: _t("Graph"),
    kanban: _t("Kanban"),
    list: _t("List"),
    map: _t("Map"),
    pivot: _t("Pivot"),
    search: _t("Search"),
};

export function viewTypeToString(vType) {
    return SUPPORTED_VIEW_TYPES[vType] || vType;
}

function isViewEditable(view) {
    return view && view in SUPPORTED_VIEW_TYPES;
}

function isStudioEditable(action) {
    if (action.type === "ir.actions.client") {
        // home_menu is somehow customizable (app creator)
        return action.tag === "menu" ? true : false;
    }
    if (action.type === "ir.actions.act_window") {
        if (action.res_model.indexOf("settings") > -1 && action.res_model.indexOf("x_") !== 0) {
            return false; // settings views aren't editable; but x_settings is
        }
        if (action.res_model === "board.board") {
            return false; // dashboard isn't editable
        }
        if (action.view_mode === "qweb") {
            // Apparently there is a QWebView that allows to
            // implement ActWindow actions that are completely custom
            // but not editable by studio
            return false;
        }
        if (action.res_model === "knowledge.article") {
            // The knowledge form view is very specific and custom, it doesn't make sense
            // to edit it. Editing the list and kanban is more debatable, but for simplicity's sake
            // we set them to not editable too.
            return false;
        }
        if (action.view_id && action.view_id[1] === "res.users.preferences.form.inherit") {
            // The employee profile view is too complex to handle inside studio.
            // @see SELF_READABLE_FIELDS.
            return false;
        }
        if (action.res_model === "account.bank.statement.line") {
            return false; // bank reconciliation isn't editable
        }
        return action.res_model ? true : false;
    }
    return false;
}

/**
 * Whether the actionService will actually load this.
 * @see action_service.js:_getActionParams
 */
function isActionStateValid(actionState) {
    return (
        actionState.action ||
        (actionState.model && (actionState.resId || actionState.view_type === "form"))
    );
}

function defaultActionForModel({ model, resId, view_id, view_type }) {
    const action = {
        res_model: model,
        type: "ir.actions.act_window",
        res_id: resId,
    };
    if (view_type === "form" || resId) {
        action.views = [[view_id || false, "form"]];
    } else {
        action.views = [[view_id || false, view_type || "list"]];
    }
    return action;
}

function getResIds(ids) {
    return (Array.isArray(ids) ? ids : [ids]).filter((id) => id && id !== "new");
}

function areActionStatesSimilar(a1, a2) {
    return a1 && a2 && (a1.action === a2.action || a1.model === a2.model);
}

function getStateToLoad(state) {
    const actionStack = state.actionStack || [];
    if (!state.action && !state.model && actionStack.length) {
        state = { ...state, ...actionStack.at(-1) };
        delete state.displayName;
    }
    return state;
}

export const studioService = {
    dependencies: ["action", "home_menu", "menu", "notification", "orm"],
    async start(env, { menu, notification, orm }) {
        function _getCurrentAction() {
            const currentController = env.services.action.currentController;
            return currentController && !currentController.virtual
                ? currentController.action
                : null;
        }
        async function loadState(state) {
            router.pushState(getStateToLoad(state), { sync: true, replace: true });
            await Promise.resolve();
            return env.services.action.loadState();
        }

        const bus = new EventBus();
        let inStudio = false;

        const menuSelectMenu = menu.selectMenu;
        menu.selectMenu = async (argMenu) => {
            if (!inStudio) {
                return menuSelectMenu.call(menu, argMenu);
            } else {
                try {
                    argMenu = typeof argMenu === "number" ? menu.getMenu(argMenu) : argMenu;
                    await open(MODES.EDITOR, argMenu.actionID);
                    menu.setCurrentMenu(argMenu);
                } catch (e) {
                    if (e instanceof NotEditableActionError) {
                        notification.add(_t("This action is not editable by Studio"), {
                            type: "danger",
                        });
                        return;
                    }
                    throw e;
                }
            }
        };

        const state = {
            studioMode: null,
            editedViewType: null,
            editedAction: null,
            editedControllerState: null,
            editorTab: "views",
            editedReport: null,
        };

        async function _loadParamsFromURL() {
            const urlState = router.current;
            if (urlState.action !== "studio") {
                return;
            }

            state.studioMode = urlState[URL_MODE_KEY];
            state.editedViewType = urlState[URL_VIEW_KEY] || null;
            const editorTab = urlState[URL_TAB_KEY] || null;
            state.editorTab = editorTab;
            if (editorTab === "reports") {
                const reportId = urlState[URL_REPORT_ID_KEY] || null;
                if (reportId) {
                    state.editedReport = { res_id: reportId };
                }
            }

            const routerActionState = urlState.actionStack?.at(-2);
            const additionalContext = {};
            if (state.studioMode === MODES.EDITOR || (!state.studioMode && routerActionState)) {
                const { active_id, active_ids } = urlState;
                if (active_id) {
                    additionalContext.active_id = active_id;
                    additionalContext.active_ids = [active_id];
                }
                if (active_ids) {
                    additionalContext.active_ids = active_ids.split(",").map(Number);
                }
                if (routerActionState?.action || routerActionState?.model) {
                    const { action, model, resId } = routerActionState;
                    if (action) {
                        state.editedAction = await env.services.action.loadAction(
                            action,
                            additionalContext
                        );
                    } else if (model) {
                        state.editedAction = defaultActionForModel(routerActionState);
                    }
                    const resIds = getResIds(resId);
                    state.editedControllerState = {
                        resId: resIds[0],
                        resIds,
                    };
                    state.studioMode = state.studioMode || MODES.EDITOR;
                    state.editorTab = state.editorTab || "views";
                    if (!state.editedViewType) {
                        if (resId) {
                            state.editedViewType = "form";
                        } else {
                            state.editedViewType = state.editedAction.views[0][1];
                        }
                    }
                }
            }
            if (!state.editedAction || !isStudioEditable(state.editedAction)) {
                state.studioMode = [undefined, MODES.EDITOR].includes(state.studioMode)
                    ? MODES.HOME_MENU
                    : state.studioMode;
                state.editedAction = null;
                state.editedViewType = null;
                state.editorTab = null;
            }
        }

        let studioProm = _loadParamsFromURL();
        routerBus.addEventListener("ROUTE_CHANGE", () => {
            studioProm = _loadParamsFromURL();
        });

        async function _openStudio(targetMode, action = false, viewType = false) {
            if (!targetMode) {
                throw new Error("mode is mandatory");
            }

            let actionStack = router.current.actionStack || [];
            const previousState = { ...state };
            if (targetMode === MODES.EDITOR) {
                let controllerState;
                if (!action) {
                    // systray open
                    const currentController = env.services.action.currentController;
                    if (currentController) {
                        actionStack = currentController.state.actionStack || [];
                        action = {
                            ...currentController.action,
                            globalState: currentController.getGlobalState?.() || {},
                        };
                        viewType = currentController.view.type;
                        controllerState = Object.assign({}, currentController.getLocalState());
                        controllerState.resIds = getResIds(
                            action.globalState.resIds || controllerState.resId
                        );
                    }
                } else {
                    let toLoad;
                    const resIds = getResIds(action.res_id);
                    if (action.id) {
                        toLoad = { action: action.path || action.id };
                    } else {
                        toLoad = {
                            displayName: action.name,
                            model: action.res_model,
                        };
                        if ((viewType || action.views?.[0]?.[1]) === "form") {
                            toLoad.resId = resIds[0] || "new";
                        }
                    }
                    actionStack = [toLoad];
                    controllerState = { resIds, resId: resIds[0] };
                }

                if (!isStudioEditable(action)) {
                    throw new NotEditableActionError();
                }
                state.editedAction = action;
                const vtype = viewType || action.views[0][1]; // fallback on first view of action
                state.editedViewType = isViewEditable(vtype) ? vtype : null;
                state.editorTab = "views";
                state.editedControllerState = controllerState || {};
            }

            state.studioMode = targetMode;

            try {
                actionStack = actionStack.filter((a) => !["menu", "studio"].includes(a.action));
                actionStack.push({
                    action: "studio",
                    [URL_MODE_KEY]: state.studioMode,
                    [URL_TAB_KEY]: state.editorTab,
                    [URL_VIEW_KEY]: state.editedViewType,
                    [URL_REPORT_ID_KEY]: state.editedReport?.id,
                });
                await loadState({ actionStack });
            } catch (e) {
                Object.assign(state, previousState);
                throw e;
            }
        }

        async function open(mode = false, actionId = false) {
            if (!mode && inStudio) {
                throw new Error("can't already be in studio");
            }
            if (!mode) {
                mode = env.services.home_menu.hasHomeMenu ? MODES.HOME_MENU : MODES.EDITOR;
            }
            let action;
            if (actionId) {
                action = await env.services.action.loadAction(actionId);
            }
            resetViewCompilerCache();
            return _openStudio(mode, action);
        }

        async function leave(actionId) {
            if (!inStudio) {
                throw new Error("leave when not in studio???");
            }
            rpcBus.trigger("CLEAR-CACHES");
            IrModelInfo.invalidate();
            // since odoo/odoo@2e891626b071a04d1a5dd3d3c40cc24a12dcb1fb
            // template cache key is composed with the name of the compiler
            // which, in studio are *usually* different.
            resetViewCompilerCache();
            const actionStack = router.current.actionStack.slice(0, -1);
            let stateLoaded = false;
            if (!actionId && state.studioMode === MODES.EDITOR && actionStack.length) {
                const lastAction = actionStack.at(-1);
                const { editedViewType, editedAction } = state;
                const defaultViewType = editedAction.views?.[0]?.[1];
                if (editedViewType) {
                    if (editedViewType === "form") {
                        const resId = state.editedControllerState?.resId || "new";
                        if (lastAction.view_type === "form" || lastAction.resId) {
                            lastAction.resId = resId;
                            delete lastAction.view_type;
                        } else {
                            actionStack.push({ ...lastAction, view_type: undefined, resId });
                        }
                    } else if (
                        lastAction.view_type === "form" &&
                        areActionStatesSimilar(lastAction, actionStack.at(-2))
                    ) {
                        actionStack.pop();
                    } else {
                        if (defaultViewType !== editedViewType) {
                            lastAction.view_type = editedViewType;
                        }
                        lastAction.resId = undefined;
                    }
                }
                const currentRouterState = { ...router.current };
                stateLoaded = await loadState({ actionStack });
                // We tried our best to leave studio with the current action's light-side sibling
                // but did not work. Revert the change in the url, and let the code fallback
                if (!stateLoaded) {
                    router.replaceState(currentRouterState, { replace: true, sync: true });
                    await Promise.resolve();
                }
            }
            if (!stateLoaded) {
                const lastValidActionIndex = actionStack.findLastIndex(isActionStateValid);
                actionId = actionId || "menu";
                let options = { clearBreadcrumbs: true };
                if (actionId === "menu" && lastValidActionIndex >= 0) {
                    options = { index: lastValidActionIndex + 1 };
                }
                await env.services.action.doAction(actionId, options);
            }
            // force rendering of the main navbar to allow adaptation of the size
            env.bus.trigger("MENUS:APP-CHANGED");
            state.studioMode = null;
        }

        async function reload(params = {}, reset = true) {
            resetViewCompilerCache();
            rpcBus.trigger("CLEAR-CACHES");
            const actionContext = state.editedAction.context;
            let additionalContext;
            if (actionContext.active_id) {
                additionalContext = { active_id: actionContext.active_id };
            }
            if (actionContext.active_ids) {
                additionalContext = Object.assign(additionalContext || {}, {
                    active_ids: actionContext.active_ids,
                });
            }
            const action = await env.services.action.loadAction(
                state.editedAction.id,
                additionalContext
            );
            setParams({ action, ...params }, reset);
        }

        function toggleHomeMenu() {
            if (!inStudio) {
                throw new Error("is it possible?");
            }
            const targetMode = [MODES.APP_CREATOR, MODES.EDITOR].includes(state.studioMode)
                ? MODES.HOME_MENU
                : MODES.EDITOR;

            const action = targetMode === MODES.EDITOR ? state.editedAction : null;
            if (targetMode === MODES.EDITOR && !action) {
                throw new Error("this button should not be clickable/visible");
            }
            const viewType = targetMode === MODES.EDITOR ? state.editedViewType : null;
            return _openStudio(targetMode, action, viewType);
        }

        function pushState() {
            const search = {};
            let replace;
            if (state._pushActionState) {
                state._pushActionState = false;
                const actionStack = [
                    { action: this.editedAction.path || this.editedAction.id },
                    { action: "studio" },
                ];
                Object.assign(search, getStateToLoad({ actionStack }));
                replace = true;
            }
            search[URL_MODE_KEY] = state.studioMode;
            search[URL_VIEW_KEY] = undefined;
            search[URL_TAB_KEY] = undefined;
            if (state.studioMode === MODES.EDITOR) {
                search[URL_VIEW_KEY] = state.editedViewType || undefined;
                search[URL_TAB_KEY] = state.editorTab;
            }
            if (state.editedAction?.context?.active_id) {
                search.active_id = state.editedAction.context.active_id;
            }

            if (state.editorTab === "reports" && state.editedReport) {
                search[URL_REPORT_ID_KEY] = state.editedReport.res_id;
            }
            router.pushState(search, { replace });
        }

        function setParams(params = {}, reset = true) {
            if ("mode" in params) {
                state.studioMode = params.mode;
            }
            if ("viewType" in params) {
                state.editedViewType = params.viewType || null;
            }
            if ("action" in params) {
                if ((state.editedAction && state.editedAction.id) !== params.action.id) {
                    state.editedControllerState = null;
                    state._pushActionState = true;
                }
                state.editedAction = params.action || null;
            }
            if ("editorTab" in params) {
                state.editorTab = params.editorTab;
                if (!("viewType" in params)) {
                    // clean me
                    state.editedViewType = null;
                }
                if (!("editedReport" in params)) {
                    state.editedReport = null;
                }
            }
            if ("editedReport" in params) {
                state.editedReport = params.editedReport;
            }
            if ("controllerState" in params) {
                state.editedControllerState = params.controllerState;
            }
            if (state.editorTab !== "reports") {
                state.editedReport = null;
            }
            bus.trigger("UPDATE", { reset });
        }

        env.bus.addEventListener("ACTION_MANAGER:UI-UPDATED", (ev) => {
            const mode = ev.detail;
            if (mode === "new") {
                return;
            }
            const action = _getCurrentAction();
            inStudio = action.tag === "studio";
        });

        const IrModelInfo = new Cache(
            async (model) =>
                await orm.call("ir.model", "studio_model_infos", [model], {
                    context: user.context,
                }),
            (model) => model
        );

        return {
            MODES,
            bus,
            isStudioEditable() {
                const action = _getCurrentAction();
                return action ? isStudioEditable(action) : false;
            },
            open,
            reload,
            pushState,
            leave,
            toggleHomeMenu,
            setParams,
            get ready() {
                return studioProm;
            },
            get mode() {
                return state.studioMode;
            },
            get editedAction() {
                return state.editedAction;
            },
            get editedViewType() {
                return state.editedViewType;
            },
            get editedControllerState() {
                return state.editedControllerState;
            },
            get editedReport() {
                return state.editedReport;
            },
            get editorTab() {
                return state.editorTab;
            },
            IrModelInfo,
        };
    },
};

registry.category("services").add("studio", studioService);

export function useStudioServiceAsReactive() {
    const studio = useService("studio");
    const state = useState({ ...studio });
    state.requestId = 1;

    function onUpdate({ detail }) {
        Object.assign(state, studio);
        if (detail.reset) {
            state.requestId++;
        }
    }
    studio.bus.addEventListener("UPDATE", onUpdate);
    onWillUnmount(() => studio.bus.removeEventListener("UPDATE", onUpdate));
    return state;
}

function actionLeave(env, action) {
    const actionId = action.context.action_id;
    return env.services.studio.leave(actionId);
}

registry.category("actions").add("action_web_studio_leave_with", actionLeave);
