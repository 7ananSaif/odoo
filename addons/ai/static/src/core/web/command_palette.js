import { Component, markRaw } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { imageUrl } from "@web/core/utils/urls";
import { DefaultCommandItem, CommandPalette } from "@web/core/commands/command_palette";
import { patch } from "@web/core/utils/patch";
import { highlightText } from "@web/core/utils/html";

const commandProviderRegistry = registry.category("command_provider");

class AskAICommand extends Component {
    static template = "ai.AskAICommand";
    static props = {
        imgUrl: String,
        ...DefaultCommandItem.props,
    };
}

async function askAIProvide(env, options) {
    const orm = env.services.orm;
    const actions = env.services.action;
    const agent = await orm.cache().call("ai.agent", "get_ask_ai_agent", []);
    if (!agent) {
        return [];
    }
    return [
        {
            action: async () => {
                const action = await orm.call("ai.agent", "action_ask_ai", [options.searchValue]);
                if (action) {
                    // Don't await so that the command palette can close immediately
                    actions.doAction(action);
                }
            },
            category: "app",
            Component: AskAICommand,
            props: {
                imgUrl: agent
                    ? imageUrl("ai.agent", agent.id, "image_128")
                    : "/ai/static/description/icon.png",
            },
            name: _t("Ask AI"),
        },
    ];
}

commandProviderRegistry.add("ask_ai", {
    namespace: "/",
    async provide(env, options) {
        return askAIProvide(env, options);
    },
});

// TODO: Add a unit test for this. The Ask AI command should be available in the default
// namespace (CTRL+K) when no commands are found.
patch(CommandPalette.prototype, {
    async setCommands(namespace, options = {}) {
        const [askAICommand] = await askAIProvide(this.env, options);
        const result = await super.setCommands(namespace, options);
        if (
            askAICommand &&
            namespace === "default" &&
            this.state.commands.length === 0 &&
            options.searchValue
        ) {
            this.state.commands = markRaw([
                {
                    ...askAICommand,
                    keyId: this.keyId++,
                    text: highlightText(
                        options.searchValue,
                        askAICommand.name,
                        "fw-bolder text-primary"
                    ),
                },
            ]);
            this.selectCommand(this.state.commands.length ? 0 : -1);
        }
        return result;
    },
});
