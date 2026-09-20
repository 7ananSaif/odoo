import { getMockEnv, makeMockEnv, serverState } from "@web/../tests/web_test_helpers";
import { getDocumentsModel } from "./data";

/**
 * Create a mocked server environment
 *
 * @param {{ serverData?: Record<string, any[]> }} [params]
 */
export async function makeDocumentsMockEnv(params) {
    if (params?.serverData) {
        for (const [modelName, records] of Object.entries(params.serverData)) {
            if (!records?.length) {
                continue;
            }
            const PyModel = getDocumentsModel(modelName);
            if (!PyModel) {
                throw new Error(`Model ${modelName} not found inside DocumentsModels`);
            }
            PyModel._records = records;
        }
    }
    const env = getMockEnv() || (await makeMockEnv());
    env.services["document.document"].store.odoobot = {
        userId: serverState.odoobotId,
    };
    return env;
}
