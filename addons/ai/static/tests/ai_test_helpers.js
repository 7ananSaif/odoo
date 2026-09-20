import { mailModels } from "@mail/../tests/mail_test_helpers";
import { AIAgent } from "./mock_server/mock_models/ai_agent";
import { defineModels } from "@web/../tests/web_test_helpers";
import { AIComposer } from "./mock_server/mock_models/ai_composer";

export function defineAIModels() {
    return defineModels(aiModels);
}

export const aiModels = { ...mailModels, AIAgent, AIComposer };
