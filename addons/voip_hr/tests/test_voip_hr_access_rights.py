from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from odoo.addons.voip.tests.test_voip_access_rights import TestVoipAccessRights


@tagged("-at_install", "post_install")
class TestVoipHrAccessRights(TestVoipAccessRights):
    def test_hr_manager_access_on_subordinates_calls(self):
        """
        HR managers have read access to voip.call records of their subordinates.
        """
        manager = new_test_user(self.env, login="manager", groups="hr.group_hr_user")
        manager_employee = self.env["hr.employee"].create(
            {
                "name": "Manager",
                "user_id": manager.id,
            },
        )
        employee_user = new_test_user(self.env, login="employee", groups="hr.group_hr_user")
        self.env["hr.employee"].create(
            {
                "name": "Employee",
                "user_id": employee_user.id,
                "parent_id": manager_employee.id,
            },
        )
        call = self.env["voip.call"].create({"user_id": employee_user.id, "phone_number": "123"})

        call.with_user(manager).read()
        with self.assertRaises(AccessError):
            self.env["voip.call"].with_user(manager).create({"user_id": employee_user.id, "phone_number": "789"})
        with self.assertRaises(AccessError):
            call.with_user(manager).write({"phone_number": "456"})
        with self.assertRaises(AccessError):
            call.with_user(manager).unlink()

    def test_department_manager_access_on_subordinates_calls(self):
        """
        Department managers have read access to voip.call records of their subordinates.
        """
        department = self.env["hr.department"].create({"name": "Hogwarts School of Witchcraft and Wizardry"})
        head_of_department = new_test_user(self.env, login="antony", groups="hr.group_hr_user")
        head_of_department_employee = self.env["hr.employee"].create(
            {
                "name": "Antony",
                "user_id": head_of_department.id,
                "department_id": department.id,
            },
        )
        department.manager_id = head_of_department_employee.id
        employee_user = new_test_user(self.env, login="employee", groups="hr.group_hr_user")
        self.env["hr.employee"].create(
            {
                "name": "Harry Potter",
                "user_id": employee_user.id,
                "department_id": department.id,
            },
        )
        call = self.env["voip.call"].create({"user_id": employee_user.id, "phone_number": "123"})

        call.with_user(head_of_department).read()
        with self.assertRaises(AccessError):
            self.env["voip.call"].with_user(head_of_department).create({"user_id": employee_user.id, "phone_number": "789"})
        with self.assertRaises(AccessError):
            call.with_user(head_of_department).write({"phone_number": "456"})
        with self.assertRaises(AccessError):
            call.with_user(head_of_department).unlink()

    def test_department_manager_access_on_non_subordinate_calls(self):
        """
        Department managers do not have any access to voip.call records for users who are not their subordinates.
        """
        department = self.env["hr.department"].create({"name": "HR", "manager_id": False})
        department_manager = new_test_user(self.env, login="manager", groups="hr.group_hr_user")
        department_manager_employee = self.env["hr.employee"].create(
            {
                "name": "Department Manager",
                "user_id": department_manager.id,
                "department_id": department.id,
            },
        )
        department.manager_id = department_manager_employee.id
        # Create a user and employee NOT in the manager's department
        outsider_user = new_test_user(self.env, login="outsider", groups="hr.group_hr_user")
        self.env["hr.employee"].create({"name": "Outsider", "user_id": outsider_user.id})

        with self.assertRaises(AccessError):
            self.env["voip.call"].with_user(department_manager).create({"user_id": outsider_user.id, "phone_number": "321"})
        outsider_call = self.env["voip.call"].create({"user_id": outsider_user.id, "phone_number": "321"})
        with self.assertRaises(AccessError):
            outsider_call.with_user(department_manager).read()
        with self.assertRaises(AccessError):
            outsider_call.with_user(department_manager).write({"phone_number": "654"})
        with self.assertRaises(AccessError):
            outsider_call.with_user(department_manager).unlink()

    def test_hr_manager_access_on_indirect_subordinate_calls(self):
        """
        HR managers also have read access to voip.call records of their indirect subordinates.
        """
        # Create a simple hierarchy: Root Manager -> Manager -> Subordinate
        root_manager = new_test_user(self.env, login="root_manager", groups="hr.group_hr_user")
        root_manager_employee = self.env["hr.employee"].create({
            "name": "Root Manager",
            "user_id": root_manager.id,
        })
        manager = new_test_user(self.env, login="manager", groups="hr.group_hr_user")
        manager_employee = self.env["hr.employee"].create({
            "name": "Manager",
            "user_id": manager.id,
            "parent_id": root_manager_employee.id,
        })
        surbodinate = new_test_user(self.env, login="employee", groups="hr.group_hr_user")
        self.env["hr.employee"].create({
            "name": "Employee",
            "user_id": surbodinate.id,
            "parent_id": manager_employee.id,
        })
        call = self.env["voip.call"].create({"user_id": surbodinate.id, "phone_number": "123"})

        call.with_user(root_manager).read()
        with self.assertRaises(AccessError):
            self.env["voip.call"].with_user(root_manager).create({"user_id": surbodinate.id, "phone_number": "789"})
        with self.assertRaises(AccessError):
            call.with_user(root_manager).write({"phone_number": "456"})
        with self.assertRaises(AccessError):
            call.with_user(root_manager).unlink()
