import { voipModels } from "@voip/../tests/voip_test_helpers";
import { defineModels } from "@web/../tests/web_test_helpers";

export function defineVoipOnsipModels() {
    return defineModels(voipOnsipModels);
}
export const voipOnsipModels = { ...voipModels };
