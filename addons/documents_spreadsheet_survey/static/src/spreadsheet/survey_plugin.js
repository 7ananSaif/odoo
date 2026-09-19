import { astToFormula, helpers, registries, EvaluationError } from "@odoo/o-spreadsheet";
import { OdooUIPlugin } from "@spreadsheet/plugins";
import { _t } from "@web/core/l10n/translation";

const { getFunctionsFromTokens, toNumber } = helpers;

export class SurveyPlugin extends OdooUIPlugin {
    static getters = [
        "getSurveyResults",
        "getSurveyIdFromPosition",
        "getSurveyUserInputIdFromPosition",
    ];
    constructor(config) {
        super(config);
        this.serverData = config.custom.odooDataProvider?.serverData;
    }

    getSurveyResults(surveyId) {
        const data = this.serverData.batch.get(
            "survey.survey",
            "get_survey_results_for_spreadsheet",
            surveyId
        );
        if (!data) {
            throw new EvaluationError(_t("Survey %s not available", surveyId));
        }
        return data;
    }

    getSurveyIdFromPosition(position) {
        const cell = this.getters.getCorrespondingFormulaCell(position);
        const evaluatedCell = this.getters.getEvaluatedCell(position);
        if (evaluatedCell.type === "error") {
            return undefined;
        }
        const sheetId = position.sheetId;
        if (cell && cell.isFormula && cell.content.startsWith("=ODOO.SURVEY(")) {
            const surveyFunction = getFunctionsFromTokens(cell.compiledFormula.tokens, [
                "ODOO.SURVEY",
            ])[0];
            if (surveyFunction) {
                try {
                    const content = astToFormula(surveyFunction.args[0]);
                    const surveyId = this.getters.evaluateFormula(sheetId, content);
                    const locale = this.getters.getLocale();
                    return toNumber(surveyId, locale);
                } catch {
                    return undefined;
                }
            }
        }
        return undefined;
    }

    getSurveyUserInputIdFromPosition(position) {
        const surveyId = this.getSurveyIdFromPosition(position);
        if (!surveyId) {
            return undefined;
        }
        const surveyUserInputIds = this.getSurveyResults(surveyId).user_input_ids;
        const surveyCell = this.getters.getCorrespondingFormulaCell(position);
        const surveyCellPosition = this.getters.getCellPosition(surveyCell.id);
        const userInputIndex = position.row - surveyCellPosition.row - 1;
        return surveyUserInputIds[userInputIndex];
    }
}

registries.featurePluginRegistry.add("SurveyPlugin", SurveyPlugin);
