import { registries, tokenColors, helpers } from "@odoo/o-spreadsheet";
import { extractDataSourceId } from "@spreadsheet/helpers/odoo_functions_helpers";

const {
    insertTokenAfterArgSeparator,
    insertTokenAfterLeftParenthesis,
    makeFieldProposal,
    unquote,
} = helpers;

registries.autoCompleteProviders.add("list_relational_fields", {
    sequence: 50,
    autoSelectFirstProposal: false,
    async getProposals(tokenAtCursor) {
        if (
            canAutoCompleteListField(tokenAtCursor) ||
            canAutoCompleteListHeaderField(tokenAtCursor)
        ) {
            const listId = extractDataSourceId(tokenAtCursor);
            if (!this.getters.isExistingList(listId)) {
                return;
            }
            const { model } = this.getters.getListDefinition(listId);
            const env = this.getters.getOdooEnv();
            let fieldNames =
                tokenAtCursor.type === "STRING" ? unquote(tokenAtCursor.value).split(".") : [];
            let fields = await loadFields(env, model, fieldNames);
            if (!fields) {
                // the last field is not a relation or an incomplete path
                fieldNames = fieldNames.slice(0, -1);
                fields = await loadFields(env, model, fieldNames);
            }
            if (!fields) {
                return;
            }
            const path = fieldNames.join(".");
            const proposals = Object.values(fields).map((field) => {
                const proposal = path
                    ? makeFieldProposal({ ...field, name: `${path}.${field.name}` })
                    : makeFieldProposal(field);
                if (field.relation) {
                    proposal.htmlContent.push({
                        value: "",
                        classes: ["oi oi-chevron-right float-end pt-1 px-1"],
                    });
                }
                return proposal;
            });
            if (path) {
                for (const proposal of proposals) {
                    const lastDotIndex = proposal.htmlContent[0].value.lastIndexOf(".");
                    proposal.htmlContent[0].value =
                        proposal.htmlContent[0].value.slice(lastDotIndex);
                }
            }
            return proposals;
        }
        return;
    },
    selectProposal: function selectListProposal(tokenAtCursor, value) {
        insertTokenAfterArgSeparator.call(this, tokenAtCursor, value);
        // move the cursor back before the double quotes to chain relations with "." ("user_id.country_id")
        const beforeClosingDoubleQuotes = this.composer.composerSelection.end - 1;
        this.composer.changeComposerCursorSelection(
            beforeClosingDoubleQuotes,
            beforeClosingDoubleQuotes
        );
    },
});

async function loadFields(env, model, fieldNames) {
    const { isInvalid, modelsInfo } = await env.services.field.loadPath(
        model,
        [...fieldNames, "*"].join(".")
    );
    if (isInvalid) {
        return;
    }
    return modelsInfo.at(-1).fieldDefs;
}

function canAutoCompleteListField(tokenAtCursor) {
    const functionContext = tokenAtCursor.functionContext;
    return (
        functionContext?.parent.toUpperCase() === "ODOO.LIST" && functionContext.argPosition === 2 // the field is the third argument: =ODOO.LIST(1,2,"email")
    );
}

function canAutoCompleteListHeaderField(tokenAtCursor) {
    const functionContext = tokenAtCursor.functionContext;
    return (
        functionContext?.parent.toUpperCase() === "ODOO.LIST.HEADER" &&
        functionContext.argPosition === 1 // the field is the second argument: =ODOO.LIST.HEADER(1,"email")
    );
}

registries.autoCompleteProviders.add("list_ids", {
    sequence: 50,
    autoSelectFirstProposal: true,
    getProposals(tokenAtCursor) {
        const functionContext = tokenAtCursor.functionContext;
        if (
            ["ODOO.LIST", "ODOO.LIST.HEADER"].includes(functionContext?.parent.toUpperCase()) &&
            functionContext.argPosition === 0
        ) {
            const listIds = this.getters.getListIds();
            return listIds.map((listId) => {
                const definition = this.getters.getListDefinition(listId);
                const str = `${listId}`;
                return {
                    text: str,
                    description: definition.name,
                    htmlContent: [{ value: str, color: tokenColors.NUMBER }],
                    fuzzySearchKey: str + definition.name,
                    alwaysExpanded: true,
                };
            });
        }
    },
    selectProposal: insertTokenAfterLeftParenthesis,
});
