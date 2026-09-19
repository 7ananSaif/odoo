import { _t } from "@web/core/l10n/translation";
import { navigateTo } from "@spreadsheet/actions/helpers";

import { registries } from "@odoo/o-spreadsheet";
const { cellMenuRegistry } = registries;

cellMenuRegistry.add("survey_see_record", {
    name: (env) => {
        const position = env.model.getters.getActivePosition();
        const surveyCell = env.model.getters.getCorrespondingFormulaCell(position);
        const surveyCellPosition = env.model.getters.getCellPosition(surveyCell.id);
        return position.row === surveyCellPosition.row
            ? _t("See survey")
            : _t("See survey participation");
    },
    sequence: 200,
    execute: surveySeeRecord,
    isVisible: canSeeSurveyRecord,
    icon: "o-spreadsheet-Icon.SEE_RECORDS",
});

function canSeeSurveyRecord(env) {
    const position = env.model.getters.getActivePosition();
    const surveyId = env.model.getters.getSurveyIdFromPosition(position);
    return surveyId !== undefined;
}

async function surveySeeRecord(env) {
    const position = env.model.getters.getActivePosition();
    const surveyId = env.model.getters.getSurveyIdFromPosition(position);
    const userInputId = env.model.getters.getSurveyUserInputIdFromPosition(position);

    if (userInputId !== undefined) {
        await navigateTo(
            env,
            "survey.action_survey_user_input",
            {
                type: "ir.actions.act_window",
                res_model: "survey.user_input",
                res_id: userInputId,
                views: [[false, "form"]],
            },
            { viewType: "form" }
        );
    } else if (surveyId !== undefined) {
        await navigateTo(
            env,
            "survey.action_survey",
            {
                type: "ir.actions.act_window",
                res_model: "survey.survey",
                res_id: surveyId,
                views: [[false, "form"]],
            },
            { viewType: "form" }
        );
    }
}
