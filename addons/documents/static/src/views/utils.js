/** @typedef {typeof import("@web/model/relational_model/record").Record} RelationalModelRecord */

/**
 * From multiple documents.document records, return the actions available on all of them.
 * @param {RelationalModelRecord[]} documents
 * @return {{id: Number, name: String}[]}
 */
export function getCommonEmbeddedActions(documents) {
    if (!documents?.length) {
        return [];
    }
    let embeddedActionsMap = new Map(
        documents[0].data.available_embedded_actions_ids?.records.map((rec) => [
            rec.resId,
            rec.data.display_name,
        ]) || []
    );
    for (const document of documents.slice(1)) {
        if (!embeddedActionsMap.size) {
            return [];
        }
        const newEmbeddedActionsMap = new Map();
        document.data.available_embedded_actions_ids.records.forEach((r) => {
            if (embeddedActionsMap.has(r.resId)) {
                newEmbeddedActionsMap.set(r.resId, r.data.display_name);
            }
        });
        embeddedActionsMap = newEmbeddedActionsMap;
    }
    const embeddedActionsArray = Array.from(embeddedActionsMap.entries());
    return embeddedActionsArray.map(([id, name]) => ({ id, name }));
}
