# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import request, route, Controller


class SurveyAnalyzeResultsRoute(Controller):
    @route('/survey/<model("survey.survey"):survey>/analyze-results', methods=['POST'], type='http', auth='user')
    def survey_analyze_results(self, survey):
        action = survey.action_survey_open_linked_spreadsheet()
        spreadsheet_id = action.get('params', {}).get('spreadsheet_id')
        return request.redirect(
            f"/odoo/surveys/{survey.id}/spreadsheet/{spreadsheet_id}"
        )
