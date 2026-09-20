# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.survey.tests.common import TestSurveyCommon
from odoo.addons.documents_spreadsheet.tests.common import SpreadsheetTestCommon

import json


class DocumentSpreadsheetSurveyAction(TestSurveyCommon, SpreadsheetTestCommon):

    def test_action_survey_open_linked_spreadsheet(self):
        test_survey = self.env["survey.survey"].create({"title": "Test Survey"})
        self.assertFalse(test_survey.spreadsheet_document_id)

        action = test_survey.action_survey_open_linked_spreadsheet()
        linked_spreadsheet = test_survey.spreadsheet_document_id
        self.assertEqual(action, {
            "type": "ir.actions.client",
            "tag": "action_open_spreadsheet",
            "params": {
                "spreadsheet_id": linked_spreadsheet.id,
            }
        })
        self.assertEqual(linked_spreadsheet.name, "Test Survey (#%s)" % test_survey.id)

        # Re-calling the action should return the same spreadsheet
        action = test_survey.action_survey_open_linked_spreadsheet()
        self.assertEqual(action["params"], {
                "spreadsheet_id": linked_spreadsheet.id,
        })

    def test_action_survey_open_linked_spreadsheet_initial_data(self):
        test_survey = self.env["survey.survey"].create({"title": "Test Survey"})
        question_0 = self._add_question(None, "What is your age", "numerical_box", survey_id=test_survey.id, sequence=1)
        answer_0 = self._add_answer(test_survey, self.customer)
        self._add_answer_line(question_0, answer_0, 25)

        test_survey.action_survey_open_linked_spreadsheet()
        binary_data = test_survey.spreadsheet_document_id.spreadsheet_data
        data = json.loads(binary_data)

        self.assertEqual(data["version"], "18.4.2")
        self.assertEqual(len(data["sheets"]), 1)
        sheet = data["sheets"][0]
        self.assertEqual(sheet["name"], "Test Survey (#%s)" % test_survey.id)
        self.assertEqual(sheet["cells"]["A1"], "=ODOO.SURVEY(%s)" % test_survey.id)
        self.assertEqual(sheet["cols"]["0"]["size"], 150)
        self.assertEqual(sheet["cols"]["1"]["size"], 150)
        self.assertEqual(sheet["panes"]["ySplit"], 1)

    def test_archived_linked_spreadsheet(self):
        test_survey = self.env["survey.survey"].create({"title": "Test Survey"})

        # Spreadsheet is restored when opening the action again
        test_survey.spreadsheet_document_id.action_archive()
        self.assertFalse(test_survey.spreadsheet_document_id.active)

        test_survey.action_survey_open_linked_spreadsheet()
        self.assertTrue(test_survey.spreadsheet_document_id.active)

        # Survey folder is restored as well
        folder_id = self.env["ir.config_parameter"].sudo().get_param('documents_spreadsheet_survey.survey_folder', False)
        folder = self.env["documents.document"].browse(int(folder_id))

        folder.action_archive()
        test_survey.spreadsheet_document_id.action_archive()
        self.assertFalse(test_survey.spreadsheet_document_id.active)
        self.assertFalse(folder.active)

        test_survey.action_survey_open_linked_spreadsheet()
        self.assertTrue(test_survey.spreadsheet_document_id.active)
        self.assertTrue(folder.active)
