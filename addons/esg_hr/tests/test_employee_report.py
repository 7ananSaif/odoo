from odoo.tests.common import TransactionCase


class TestEmployeeReport(TransactionCase):
    def test_leadership_level(self):
        """
        Leadership Level represents the maximum number of levels of subordinates under a given employee.
        For instance, given the following diagram of an employee hierarchy:

                         ┌──────────┐
                         │Employee 1│
                 ┌───────┴────┬─────┴───────┐
                 │            │             │
            ┌────▼─────┐ ┌────▼─────┐ ┌─────▼────┐
            │Employee 2│ │Employee 3│ │Employee 4│
            └────┬─────┘ └──────────┘ └──────────┘
                 │
            ┌────▼─────┐
            │Employee 5│
            └──────────┘

        We have the following values for leadership level:
        - Employee 1: 2
        - Employee 2: 1
        - Employees 3, 4 and 5: 0

        In case of cycles, the maximum depth will be the one that can be reached
        without encountering the same employee again.
        """
        employee_1 = self.env["hr.employee"].create({
            "name": "Employee 1",
        })
        employee_2, employee_3, employee_4 = self.env["hr.employee"].create([{
            "name": f"Employee {n}",
            "parent_id": employee_1.id,
        } for n in range(2, 5)])
        employee_5 = self.env["hr.employee"].create({
            "name": "Employee 5",
            "parent_id": employee_2.id,
        })

        for employee, expected_leadership_level in [
            (employee_1, 2),
            (employee_2, 1),
            (employee_3, 0),
            (employee_5, 0),
        ]:
            report_record = self.env["esg.employee.report"].browse(employee.id)
            self.assertEqual(report_record.leadership_level, expected_leadership_level)

        # Add a cycle
        employee_1.parent_id = employee_4.id
        self.env.cr.flush()
        self.env["esg.employee.report"]._invalidate_cache()
        self.env["hr.employee"]._invalidate_cache()
        for employee, expected_leadership_level in [
            (employee_1, 2),    # Longest path is unchaged since the cycle is only 1 -> 4 -> 1 (depth of one)
            (employee_4, 3),    # Since the longest path is now 4 -> 1 -> 2 -> 5
        ]:
            report_record = self.env["esg.employee.report"].browse(employee.id)
            self.assertEqual(report_record.leadership_level, expected_leadership_level)

        # Make employees their own manager
        employee_1.parent_id = employee_1.id
        employee_4.parent_id = employee_4.id
        self.env.cr.flush()
        self.env["esg.employee.report"]._invalidate_cache()
        self.env["hr.employee"]._invalidate_cache()
        for employee, expected_leadership_level in [
            (employee_1, 2),    # Longest path still unchanged
            (employee_4, 0),    # Employee 4 is now isolated from the rest of the hierarchy
        ]:
            report_record = self.env["esg.employee.report"].browse(employee.id)
            self.assertEqual(report_record.leadership_level, expected_leadership_level)
