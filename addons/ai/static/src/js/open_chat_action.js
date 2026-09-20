import { registry } from "@web/core/registry";

async function initChat(env, action) {
    const store = env.services["mail.store"];

    const thread = await store.Thread.getOrFetch({
        model: "discuss.channel",
        id: Number(action.params.channelId),
    });
    if (!thread) {
        throw new Error("Thread not found");
    }
    thread.open({ focus: true });
    await thread.isLoadedDeferred;
    if (action.params.user_prompt && thread.status !== "loading") {
        await thread.post(action.params.user_prompt);
    }
}

registry.category("actions").add("agent_chat_action", initChat);
