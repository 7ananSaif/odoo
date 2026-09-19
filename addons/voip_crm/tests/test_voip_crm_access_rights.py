from odoo.exceptions import AccessError
from odoo.tests import common, tagged
from odoo.tests.common import new_test_user


@tagged("-at_install", "post_install")
class TestVoipCrmAccessRights(common.TransactionCase):
    def test_team_leader_access_on_subordinates_calls(self):
        """
        Sales team leaders can read voip.call records of users on their team.
        They can't create, write, or delete them.
        """
        team_leader = new_test_user(self.env, login="team_leader", groups="sales_team.group_sale_salesman")
        team = self.env["crm.team"].create({"name": "Sales Team", "user_id": team_leader.id})
        team_member = new_test_user(self.env, login="team_member", groups="sales_team.group_sale_salesman")
        team.write({"member_ids": [team_member.id, team_leader.id]})
        call_made_by_team_member = self.env["voip.call"].create({"phone_number": "555", "user_id": team_member.id})
        call_made_by_team_member.with_user(team_leader).read()

        with self.assertRaises(AccessError):
            self.env["voip.call"].with_user(team_leader).create({"user_id": team_member.id, "phone_number": "888"})
        with self.assertRaises(AccessError):
            call_made_by_team_member.with_user(team_leader).write({"phone_number": "999"})
        with self.assertRaises(AccessError):
            call_made_by_team_member.with_user(team_leader).unlink()

    def test_team_leader_access_on_non_subordinate_calls(self):
        """
        Sales team leaders do not have any access to voip.call records for users who are not on their team.
        """
        team_leader = new_test_user(self.env, login="team_leader", groups="sales_team.group_sale_salesman")
        self.env["crm.team"].create({"name": "Sales Team", "user_id": team_leader.id})
        not_in_the_team = new_test_user(self.env, login="not_in_the_team", groups="sales_team.group_sale_salesman")
        call_made_by_outsider = self.env["voip.call"].create({"phone_number": "777", "user_id": not_in_the_team.id})

        with self.assertRaises(AccessError):
            self.env["voip.call"].with_user(team_leader).create({"user_id": not_in_the_team.id, "phone_number": "777"})
        with self.assertRaises(AccessError):
            call_made_by_outsider.with_user(team_leader).read()
        with self.assertRaises(AccessError):
            call_made_by_outsider.with_user(team_leader).write({"phone_number": "888"})
        with self.assertRaises(AccessError):
            call_made_by_outsider.with_user(team_leader).unlink()
