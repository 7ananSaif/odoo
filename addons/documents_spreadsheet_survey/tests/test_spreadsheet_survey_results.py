# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.survey.tests.common import TestSurveyCommon
from odoo.addons.documents_spreadsheet.tests.common import SpreadsheetTestCommon

from odoo.addons.spreadsheet.utils.formatting import datetime_to_spreadsheet_date_number


class DocumentSpreadsheetSurveyResults(TestSurveyCommon, SpreadsheetTestCommon):

    def test_get_simple_survey_results(self):
        test_survey = self.env["survey.survey"].create({"title": "Test Survey"})
        question_0 = self._add_question(None, "What is your age", "numerical_box", survey_id=test_survey.id, sequence=1)
        answer_0 = self._add_answer(test_survey, self.customer)
        self._add_answer_line(question_0, answer_0, 25)
        tz_name = self.env.user.tz or 'UTC'

        spreadsheet_survey_results = test_survey.get_survey_results_for_spreadsheet()[0]
        spreadsheet_survey_results_table = spreadsheet_survey_results["survey_table"]
        self.assertEqual(len(spreadsheet_survey_results_table), 2)
        self.assertEqual(len(spreadsheet_survey_results_table[0]), 2)
        self.assertEqual(spreadsheet_survey_results_table[0][0]["value"], "Timestamp")
        self.assertEqual(spreadsheet_survey_results_table[0][1]["value"], datetime_to_spreadsheet_date_number(answer_0.create_date, tz_name))
        self.assertEqual(spreadsheet_survey_results_table[0][1]["format"], "mm/dd/yyyy hh:mm:ss a")
        self.assertEqual(spreadsheet_survey_results_table[1][0]["value"], "What is your age")
        self.assertEqual(spreadsheet_survey_results_table[1][1]["value"], 25)

        self.assertEqual(spreadsheet_survey_results["user_input_ids"], [answer_0.id])

    def test_get_survey_results_multiple_answers(self):
        peterParker = self.env["res.partner"].create({"name": "Peter Parker"})
        tz_name = self.env.user.tz or 'UTC'

        test_survey = self.env["survey.survey"].create({"title": "Test Survey"})
        question_0 = self._add_question(None, "How are you?", "char_box", survey_id=test_survey.id, sequence=1)

        answer_0 = self._add_answer(test_survey, self.customer)
        self._add_answer_line(question_0, answer_0, "Good")

        answer_1 = self._add_answer(test_survey, peterParker)
        self._add_answer_line(question_0, answer_1, "Mr. Stark I Don't feel so good")

        spreadsheet_survey_results = test_survey.get_survey_results_for_spreadsheet()[0]
        spreadsheet_survey_results_table = spreadsheet_survey_results["survey_table"]

        self.assertEqual(spreadsheet_survey_results_table[0][0]["value"], "Timestamp")
        self.assertEqual(spreadsheet_survey_results_table[0][1]["value"], datetime_to_spreadsheet_date_number(answer_0.create_date, tz_name))
        self.assertEqual(spreadsheet_survey_results_table[0][2]["value"], datetime_to_spreadsheet_date_number(answer_1.create_date, tz_name))

        self.assertEqual(spreadsheet_survey_results_table[1][0]["value"], "How are you?")
        self.assertEqual(spreadsheet_survey_results_table[1][1]["value"], "Good")
        self.assertEqual(spreadsheet_survey_results_table[1][2]["value"], "Mr. Stark I Don't feel so good")
        self.assertEqual(spreadsheet_survey_results["user_input_ids"], [answer_0.id, answer_1.id])

    def test_get_survey_results_multiple_questions(self):
        test_survey = self.env["survey.survey"].create({"title": "Test Survey"})
        question_0 = self._add_question(None, "How are you?", "char_box", survey_id=test_survey.id, sequence=1)
        q1 = self._add_question(None, "What is your age", "numerical_box", survey_id=test_survey.id, sequence=2)
        tz_name = self.env.user.tz or 'UTC'

        answer_0 = self._add_answer(test_survey, self.customer)
        self._add_answer_line(question_0, answer_0, "Good")
        self._add_answer_line(q1, answer_0, 25)

        spreadsheet_survey_results = test_survey.get_survey_results_for_spreadsheet()[0]["survey_table"]

        self.assertEqual(spreadsheet_survey_results[0][0]["value"], "Timestamp")
        self.assertEqual(spreadsheet_survey_results[0][1]["value"], datetime_to_spreadsheet_date_number(answer_0.create_date, tz_name))
        self.assertEqual(spreadsheet_survey_results[1][0]["value"], "How are you?")
        self.assertEqual(spreadsheet_survey_results[1][1]["value"], "Good")
        self.assertEqual(spreadsheet_survey_results[2][0]["value"], "What is your age")
        self.assertEqual(spreadsheet_survey_results[2][1]["value"], 25)

    def test_get_survey_results_simple_choice_question_with_comment(self):
        test_survey = self.env["survey.survey"].create({"title": "Test Survey"})
        q_comments = self._add_question(
            None, "What are cats ?", "simple_choice", survey_id=test_survey.id,
            comments_allowed=True, comment_count_as_answer=False,
            sequence=1, labels=[{"value": "Cute"}, {"value": "Mammals"}, {"value": "Gods"}])
        q_comment_as_answer = self._add_question(
            None, "What are dogs ?", "simple_choice", survey_id=test_survey.id,
            comments_allowed=True, comment_count_as_answer=True,
            sequence=1, labels=[{"value": "Smart"}, {"value": "Brave"}])

        answer_0 = self._add_answer(test_survey, self.customer)
        self._add_answer_line(q_comments, answer_0, q_comments.suggested_answer_ids.ids[0])
        self._add_comment(test_survey, q_comments, answer_0, "this is a comment")
        self._add_comment(test_survey, q_comment_as_answer, answer_0, "good boys")

        spreadsheet_survey_results = test_survey.get_survey_results_for_spreadsheet()[0]["survey_table"]
        self.assertEqual(spreadsheet_survey_results[1][0]["value"], "What are cats ?")
        self.assertEqual(spreadsheet_survey_results[1][1]["value"], "Cute")
        self.assertEqual(spreadsheet_survey_results[2][0]["value"], "Comments - What are cats ?")
        self.assertEqual(spreadsheet_survey_results[2][1]["value"], "this is a comment")
        self.assertEqual(spreadsheet_survey_results[3][0]["value"], "What are dogs ?")
        self.assertEqual(spreadsheet_survey_results[3][1]["value"], "good boys")

    def test_get_survey_results_multiple_choice_question(self):
        test_survey = self.env["survey.survey"].create({"title": "Test Survey"})
        question_0 = self._add_question(
            None, "What are cats ?", "multiple_choice", survey_id=test_survey.id,
            sequence=1, labels=[{"value": "Cute"}, {"value": "Mammals"}, {"value": "Gods"}])
        answer_0 = self._add_answer(test_survey, self.customer)
        self._add_answer_line(question_0, answer_0, question_0.suggested_answer_ids.ids[0])
        self._add_answer_line(question_0, answer_0, question_0.suggested_answer_ids.ids[1])

        spreadsheet_survey_results = test_survey.get_survey_results_for_spreadsheet()[0]["survey_table"]
        self.assertEqual(spreadsheet_survey_results[1][0]["value"], "What are cats ?")
        self.assertEqual(spreadsheet_survey_results[1][1]["value"], "Cute, Mammals")

    def test_get_survey_results_multiple_choice_question_with_comments(self):
        test_survey = self.env["survey.survey"].create({"title": "Test Survey"})
        q_comments = self._add_question(
            None, "What are cats ?", "multiple_choice", survey_id=test_survey.id,
            comments_allowed=True, comment_count_as_answer=False,
            sequence=1, labels=[{"value": "Cute"}, {"value": "Mammals"}, {"value": "Gods"}])
        q_comment_as_answer = self._add_question(
            None, "What are dogs ?", "multiple_choice", survey_id=test_survey.id,
            comments_allowed=True, comment_count_as_answer=True,
            sequence=1, labels=[{"value": "Smart"}, {"value": "Brave"}])

        answer_0 = self._add_answer(test_survey, self.customer)
        self._add_answer_line(q_comments, answer_0, q_comments.suggested_answer_ids.ids[0])
        self._add_comment(test_survey, q_comments, answer_0, "this is a comment")
        self._add_answer_line(q_comment_as_answer, answer_0, q_comment_as_answer.suggested_answer_ids.ids[0])
        self._add_comment(test_survey, q_comment_as_answer, answer_0, "good boys")

        spreadsheet_survey_results = test_survey.get_survey_results_for_spreadsheet()[0]["survey_table"]
        self.assertEqual(spreadsheet_survey_results[1][0]["value"], "What are cats ?")
        self.assertEqual(spreadsheet_survey_results[1][1]["value"], "Cute")
        self.assertEqual(spreadsheet_survey_results[2][0]["value"], "Comments - What are cats ?")
        self.assertEqual(spreadsheet_survey_results[2][1]["value"], "this is a comment")
        self.assertEqual(spreadsheet_survey_results[3][0]["value"], "What are dogs ?")
        self.assertEqual(spreadsheet_survey_results[3][1]["value"], "Smart, good boys")

    def test_get_survey_results_matrix_question(self):
        test_survey = self.env["survey.survey"].create({"title": "Test Survey"})
        question_0 = self._add_question(
            None, "When do you harvest those fruits", "matrix", survey_id=test_survey.id, sequence=1,
            labels=[{"value": "Spring"}, {"value": "Summer"}],
            labels_2=[{"value": "Apples"}, {"value": "Strawberries"}])
        answer_0 = self._add_answer(test_survey, self.customer)
        [apples_row_id, strawberries_row_id] = question_0.matrix_row_ids.ids
        [spring_id, summer_id] = question_0.suggested_answer_ids.ids
        self._add_answer_line(question_0, answer_0, spring_id, answer_value_row=apples_row_id)
        self._add_answer_line(question_0, answer_0, summer_id, answer_value_row=strawberries_row_id)

        spreadsheet_survey_results = test_survey.get_survey_results_for_spreadsheet()[0]["survey_table"]
        self.assertEqual(spreadsheet_survey_results[1][0]["value"], "When do you harvest those fruits [Apples]")
        self.assertEqual(spreadsheet_survey_results[1][1]["value"], "Spring")
        self.assertEqual(spreadsheet_survey_results[2][0]["value"], "When do you harvest those fruits [Strawberries]")
        self.assertEqual(spreadsheet_survey_results[2][1]["value"], "Summer")

    def test_get_survey_results_matrix_question_with_comments(self):
        test_survey = self.env["survey.survey"].create({"title": "Test Survey"})
        question_0 = self._add_question(
            None, "When do you harvest those fruits", "matrix", survey_id=test_survey.id, sequence=1,
            comments_allowed=True, comment_count_as_answer=False,
            labels=[{"value": "Spring"}, {"value": "Summer"}],
            labels_2=[{"value": "Apples"}, {"value": "Strawberries"}])
        answer_0 = self._add_answer(test_survey, self.customer)
        [apples_row_id, _] = question_0.matrix_row_ids.ids
        [spring_id, _] = question_0.suggested_answer_ids.ids
        self._add_answer_line(question_0, answer_0, spring_id, answer_value_row=apples_row_id)
        self._add_comment(test_survey, question_0, answer_0, "this is a comment")

        spreadsheet_survey_results = test_survey.get_survey_results_for_spreadsheet()[0]["survey_table"]
        self.assertEqual(spreadsheet_survey_results[1][0]["value"], "When do you harvest those fruits [Apples]")
        self.assertEqual(spreadsheet_survey_results[1][1]["value"], "Spring")
        self.assertEqual(spreadsheet_survey_results[2][0]["value"], "When do you harvest those fruits [Strawberries]")
        self.assertEqual(spreadsheet_survey_results[2][1]["value"], "")
        self.assertEqual(spreadsheet_survey_results[3][0]["value"], "Comments - When do you harvest those fruits")
        self.assertEqual(spreadsheet_survey_results[3][1]["value"], "this is a comment")

    def test_results_login_required(self):
        test_survey = self.env["survey.survey"].create({"title": "Test Survey", "users_login_required": True})
        question_0 = self._add_question(None, "What is your age", "numerical_box", survey_id=test_survey.id, sequence=1)
        answer_0 = self._add_answer(test_survey, self.customer)
        self._add_answer_line(question_0, answer_0, 25)

        spreadsheet_survey_results = test_survey.get_survey_results_for_spreadsheet()[0]["survey_table"]
        self.assertEqual(spreadsheet_survey_results[1][0]["value"], "User")
        self.assertEqual(spreadsheet_survey_results[1][1]["value"], self.customer.name)

    def test_results_limited_attempts(self):
        test_survey = self.env["survey.survey"].create({
            "title": "Test Survey",
            "users_login_required": True,
            "is_attempts_limited": True,
            "attempts_limit": 3
        })
        question_0 = self._add_question(None, "How many finger do I have ?", "numerical_box", survey_id=test_survey.id, sequence=1)
        answer_0 = self._add_answer(test_survey, self.customer)
        self._add_answer_line(question_0, answer_0, 4)

        spreadsheet_survey_results = test_survey.get_survey_results_for_spreadsheet()[0]["survey_table"]
        self.assertEqual(spreadsheet_survey_results[1][0]["value"], "User")
        self.assertEqual(spreadsheet_survey_results[1][1]["value"], self.customer.name)
        self.assertEqual(spreadsheet_survey_results[2][0]["value"], "Attempts")
        self.assertEqual(spreadsheet_survey_results[2][1]["value"], 1)
        self.assertEqual(spreadsheet_survey_results[2][1]["format"], '0"/3"')

    def test_results_scored_survey(self):
        test_survey = self.env["survey.survey"].create({
            "title": "Test Survey",
            "scoring_type": "scoring_with_answers",
            "scoring_success_min": 50,
        })
        question_0 = self._add_question(
            None, 'Question 1', 'simple_choice',
            sequence=2,
            survey_id=test_survey.id,
            labels=[
                {'value': 'Wrong answer'},
                {'value': 'Correct answer', 'is_correct': True, 'answer_score': 1.0}
            ])
        answer_0 = self._add_answer(test_survey, self.customer)
        self._add_answer_line(question_0, answer_0, question_0.suggested_answer_ids.ids[0])
        answer_1 = self._add_answer(test_survey, self.customer)
        self._add_answer_line(question_0, answer_1, question_0.suggested_answer_ids.ids[1])

        spreadsheet_survey_results = test_survey.get_survey_results_for_spreadsheet()[0]["survey_table"]

        self.assertEqual(spreadsheet_survey_results[1][0]["value"], "Score (%)")
        self.assertEqual(spreadsheet_survey_results[1][1]["value"], 0.00)
        self.assertEqual(spreadsheet_survey_results[1][1]["format"], '0.00%')
        self.assertEqual(spreadsheet_survey_results[1][2]["value"], 1.00)
        self.assertEqual(spreadsheet_survey_results[1][2]["format"], '0.00%')
        self.assertEqual(spreadsheet_survey_results[2][0]["value"], "Quiz passed")
        self.assertEqual(spreadsheet_survey_results[2][1]["value"], False)
        self.assertEqual(spreadsheet_survey_results[2][2]["value"], True)

    def _add_comment(self, survey, question, user_input, comment_value):
        self.env['survey.user_input.line'].create({
            'survey_id': survey.id,
            'question_id': question.id,
            'user_input_id': user_input.id,
            'answer_type': 'char_box',
            'value_char_box': comment_value
        })
