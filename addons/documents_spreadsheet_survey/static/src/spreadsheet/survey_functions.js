/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

import { helpers, registries } from "@odoo/o-spreadsheet";
const { arg, toNumber } = helpers;

registries.functionRegistry.add("ODOO.SURVEY", {
    description: _t("Return the results of a survey."),
    args: [arg("survey_id (number)", _t("The survey id"))],
    category: "Odoo",
    compute: function (surveyId) {
        surveyId = toNumber(surveyId, this.locale);
        return this.getters.getSurveyResults(surveyId).survey_table;
    },
});
