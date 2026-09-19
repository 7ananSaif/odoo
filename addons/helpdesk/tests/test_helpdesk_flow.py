# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from .common import HelpdeskCommon
from odoo.exceptions import AccessError
from odoo.fields import Command
from odoo.tests import Form
from odoo.tests.common import users


class TestHelpdeskFlow(HelpdeskCommon):
    """ Test used to check that the base functionalities of Helpdesk function as expected.
        - test_access_rights: tests a few access rights constraints
        - test_assign_close_dates: tests the assignation and closing time get computed correctly
        - test_ticket_partners: tests the number of tickets of a partner is computed correctly
        - test_team_assignation_[method]: tests the team assignation method work as expected
        - test_automatic_ticket_closing: tests automatic ticket closing after set number of days
    """

    def test_access_rights(self):
        # helpdesk user should only be able to:
        #   read: teams, stages, SLAs,
        #   read, create, write, unlink: tickets, tags
        # helpdesk manager:
        #   read, create, write, unlink: everything (from helpdesk)
        # we consider in these tests that if the user can do it, the manager can do it as well (as the group is implied)
        def test_write_and_unlink(record):
            record.write({'name': 'test_write'})
            record.unlink()

        def test_not_write_and_unlink(self, record):
            with self.assertRaises(AccessError):
                record.write({'name': 'test_write'})
            with self.assertRaises(AccessError):
                record.unlink()
            # self.assertRaises(AccessError, record.write({'name': 'test_write'})) # , "Helpdesk user should not be able to write on %s" % record._name)
            # self.assertRaises(AccessError, record.unlink(), "Helpdesk user could unlink %s" % record._name)

        # helpdesk.team access rights
        team = self.env['helpdesk.team'].with_user(self.helpdesk_manager).create({'name': 'test'})
        team.with_user(self.helpdesk_user).read()
        test_not_write_and_unlink(self, team.with_user(self.helpdesk_user))
        with self.assertRaises(AccessError):
            team.with_user(self.helpdesk_user).create({'name': 'test create'})
        test_write_and_unlink(team)

        # helpdesk.ticket access rights
        ticket = self.env['helpdesk.ticket'].with_user(self.helpdesk_user).create({'name': 'test'})
        ticket.read()
        test_write_and_unlink(ticket)

        # helpdesk.stage access rights
        stage = self.env['helpdesk.stage'].with_user(self.helpdesk_manager).create({
            'name': 'test',
            'team_ids': [(6, 0, [self.test_team.id])],
        })
        stage.with_user(self.helpdesk_user).read()
        test_not_write_and_unlink(self, stage.with_user(self.helpdesk_user))
        with self.assertRaises(AccessError):
            stage.with_user(self.helpdesk_user).create({
                'name': 'test create',
                'team_ids': [(6, 0, [self.test_team.id])],
            })
        test_write_and_unlink(stage)

        # helpdesk.sla access rights
        sla = self.env['helpdesk.sla'].with_user(self.helpdesk_manager).create({
            'name': 'test',
            'team_id': self.test_team.id,
            'stage_id': self.stage_done.id,
        })
        sla.with_user(self.helpdesk_user).read()
        test_not_write_and_unlink(self, sla.with_user(self.helpdesk_user))
        with self.assertRaises(AccessError):
            sla.with_user(self.helpdesk_user).create({
                'name': 'test create',
                'team_id': self.test_team.id,
                'stage_id': self.stage_done.id,
            })
        test_write_and_unlink(sla)

        # helpdesk.tag access rights
        tag = self.env['helpdesk.tag'].with_user(self.helpdesk_user).create({'name': 'test with unique name please'})
        tag.read()
        test_write_and_unlink(tag)

    def test_assign_close_dates(self):
        # helpdesk user create a ticket
        with self._ticket_patch_now('2019-01-08 12:00:00'):
            ticket1 = self.env['helpdesk.ticket'].with_user(self.helpdesk_user).create({
                'name': 'test ticket 1',
                'team_id': self.test_team.id,
            })

        with self._ticket_patch_now('2019-01-10 13:00:00'):
            # the helpdesk user takes the ticket
            ticket1.user_id = self.helpdesk_user
            # we verify the ticket is correctly assigned
            self.assertEqual(ticket1.user_id.id, ticket1.env.uid, "Assignation for ticket not correct")
            self.assertEqual(ticket1.assign_hours, 17, "Assignation time for ticket not correct")

        with self._ticket_patch_now('2019-01-10 15:00:00'):
            # we close the ticket and verify its closing time
            ticket1.write({'stage_id': self.stage_done.id})
            self.assertEqual(ticket1.close_hours, 19, "Close time for ticket not correct")

    def test_ticket_ref_ordering(self):
        ticket_sequence = self.env['ir.sequence'].search([('code', '=', 'helpdesk.ticket')])
        ticket_sequence.padding = 2
        ticket_sequence.number_next_actual = 99
        tickets = self.env['helpdesk.ticket'].create([
            {
                'name': 'test ticket_ref ordering',
                'team_id': self.test_team.id,
            },
            {
                'name': 'test ticket_ref ordering',
                'team_id': self.test_team.id,
            },
        ])
        self.assertTrue(tickets[0].ticket_ref > tickets[1].ticket_ref)  # '99' > '100'

        ticket_search = tickets.search([('name', '=', 'test ticket_ref ordering')], order='ticket_ref ASC')
        self.assertEqual(ticket_search[0], tickets[0], "Ticket created first appears first in order")
        self.assertEqual(ticket_search[1], tickets[1])

    def test_ticket_partners(self):
        # we create a partner
        partner = self.env['res.partner'].create({
            'name': 'Freddy Krueger'
        })
        # helpdesk user creates 2 tickets for the partner
        ticket1 = self.env['helpdesk.ticket'].with_user(self.helpdesk_user).create({
            'name': 'partner ticket 1',
            'team_id': self.test_team.id,
            'partner_id': partner.id,
        })
        self.env['helpdesk.ticket'].with_user(self.helpdesk_user).create({
            'name': 'partner ticket 2',
            'team_id': self.test_team.id,
            'partner_id': partner.id,
        })
        self.assertTrue(ticket1.partner_ticket_count == 1, "Incorrect number of tickets from the same partner.")

    def test_team_assignation_randomly(self):
        # we put the helpdesk user and manager in the test_team's members
        self.test_team.member_ids = [(6, 0, [self.helpdesk_user.id, self.helpdesk_manager.id])]
        # we set the assignation method to randomly (=uniformly distributed)
        self.test_team.update({'assign_method': 'randomly', 'auto_assignment': True})
        # we create a bunch of tickets
        self.env['helpdesk.ticket'].create([{
            'name': 'test ticket ' + str(i),
            'team_id': self.test_team.id,
        } for i in range(5)])
        # add unassigned ticket to test if the distribution is kept equal.
        self.env['helpdesk.ticket'].create({
            'name': 'ticket unassigned',
            'team_id': self.test_team.id,
            'user_id': False,
        })

        self.env['helpdesk.ticket'].create([{
            'name': 'test ticket ' + str(i),
            'team_id': self.test_team.id,
        } for i in range(5, 12)])
        # ensure both members have the same amount of tickets assigned
        self.assertEqual(self.env['helpdesk.ticket'].search_count([('user_id', '=', self.helpdesk_user.id)]), 6)
        self.assertEqual(self.env['helpdesk.ticket'].search_count([('user_id', '=', self.helpdesk_manager.id)]), 6)

        # tickets created in a folded stage should not be assigned
        closed_ticket = self.env['helpdesk.ticket'].create({
            'name': 'closed ticket',
            'team_id': self.test_team.id,
            'stage_id': self.stage_done.id,
        })
        self.assertFalse(closed_ticket.user_id, "The ticket should not have been assigned because it was created in a folded stage")

        assigned_closed_ticket = self.env['helpdesk.ticket'].create({
            'name': 'assigned closed ticket',
            'team_id': self.test_team.id,
            'stage_id': self.stage_done.id,
            'user_id': self.helpdesk_user.id,
        })
        self.assertEqual(assigned_closed_ticket.user_id.id, self.helpdesk_user.id, "The ticket should be assigned even though it was created in a folded stage, because the assignee was explicitely given.")

    def test_team_assignation_balanced(self):
        # we put the helpdesk user and manager in the test_team's members
        self.test_team.member_ids = [(6, 0, [self.helpdesk_user.id, self.helpdesk_manager.id])]
        # we set the assignation method to randomly (=uniformly distributed)
        self.test_team.update({'assign_method': 'balanced', 'auto_assignment': True})
        # we create a bunch of tickets
        self.env['helpdesk.ticket'].create([{
            'name': 'test ticket ' + str(i),
            'team_id': self.test_team.id,
        } for i in range(4)])
        # ensure both members have the same amount of tickets assigned
        self.assertEqual(self.env['helpdesk.ticket'].search_count([('user_id', '=', self.helpdesk_user.id)]), 2)
        self.assertEqual(self.env['helpdesk.ticket'].search_count([('user_id', '=', self.helpdesk_manager.id)]), 2)

        # helpdesk user finishes his 2 tickets
        self.env['helpdesk.ticket'].search([('user_id', '=', self.helpdesk_user.id)]).write({'stage_id': self.stage_done.id})

        # we create 4 new tickets
        self.env['helpdesk.ticket'].create([{
            'name': 'test ticket ' + str(i),
            'team_id': self.test_team.id,
        } for i in range(4)])

        # ensure both members have the same amount of tickets assigned
        self.assertEqual(self.env['helpdesk.ticket'].search_count([('user_id', '=', self.helpdesk_user.id), ('close_date', '=', False)]), 3)
        self.assertEqual(self.env['helpdesk.ticket'].search_count([('user_id', '=', self.helpdesk_manager.id), ('close_date', '=', False)]), 3)

        # tickets created in a folded stage should not be assigned
        closed_ticket = self.env['helpdesk.ticket'].create({
            'name': 'closed ticket',
            'team_id': self.test_team.id,
            'stage_id': self.stage_done.id,
        })
        self.assertFalse(closed_ticket.user_id, "The ticket should not have been assigned because it was created in a folded stage")

    def test_team_assignation_tags(self):
        self.test_team.update({'assign_method': 'tags', 'auto_assignment': True})
        tags = self.env['helpdesk.tag'].create([{
            'name': f"tag_{i}",
        } for i in range(3)])

        ticket = self.env['helpdesk.ticket'].create({
            'name': "Test Ticket",
            'team_id': self.test_team.id,
            'tag_ids': [Command.link(tags[2].id)],
        })
        self.assertFalse(ticket.user_id, "The ticket should not be assigned since the tag/users map is empty.")

        self.env['helpdesk.tag.assignment'].create([{
            'team_id': self.test_team.id,
            'tag_id': tags[0].id,
            'user_ids': [Command.link(user_id) for user_id in [self.helpdesk_user.id, self.helpdesk_manager.id]],
        }, {
            'team_id': self.test_team.id,
            'tag_id': tags[1].id,
            'user_ids': [Command.link(self.helpdesk_manager.id)],
        }])

        self.env['helpdesk.ticket'].create([{
            'name': f"Test Ticket {i}",
            'team_id': self.test_team.id,
            'user_id': self.helpdesk_user.id,
        } for i in range(3)])

        self.env['helpdesk.ticket'].create([{
            'name': f"Ticket {i}",
            'team_id': self.test_team.id,
            'tag_ids': [Command.link(tags[0].id)],
        } for i in range(5)])
        # Both users should now have an equal amount of open tickets
        self.assertEqual(self.env['helpdesk.ticket'].search_count([('user_id', '=', self.helpdesk_user.id)]), 4)
        self.assertEqual(self.env['helpdesk.ticket'].search_count([('user_id', '=', self.helpdesk_manager.id)]), 4)

        ticket = self.env['helpdesk.ticket'].create({
            'name': "Test Ticket",
            'team_id': self.test_team.id,
            'tag_ids': [Command.link(tags[1].id)],
            'user_id': self.helpdesk_user.id,
        })
        self.assertEqual(ticket.user_id, self.helpdesk_user, "The ticket should not get reassigned if it's already assigned.")

        ticket = self.env['helpdesk.ticket'].create({
            'name': "Test Ticket",
            'team_id': self.test_team.id,
            'tag_ids': [Command.link(tags[2].id)],
        })
        self.assertFalse(ticket.user_id, "The ticket should not get assigned if there is no match in the mapping.")

        ticket = self.env['helpdesk.ticket'].create({
            'name': "Test Ticket",
            'team_id': self.test_team.id,
        })
        self.assertFalse(ticket.user_id, "Ticket should not be assigned yet, as is has no tag.")
        ticket.write({'tag_ids': [Command.link(tags[1].id)]})
        self.assertEqual(ticket.user_id, self.helpdesk_manager, "Adding the tag on a existing unassigned ticket should assign it.")
        ticket.write({'tag_ids': [Command.unlink(tags[1].id)]})
        self.assertEqual(ticket.user_id, self.helpdesk_manager, "Removing the tag should have no effect.")

        ticket = self.env['helpdesk.ticket'].create({
            'name': "Test Ticket",
            'team_id': self.test_team.id,
            'user_id': self.helpdesk_user.id,
        })
        ticket.write({'tag_ids': [Command.link(tags[1].id)]})
        self.assertEqual(ticket.user_id, self.helpdesk_user, "Adding the tag on a existing assigned ticket should have no effect.")

        ticket = self.env['helpdesk.ticket'].create({
            'name': "Test Ticket",
            'team_id': self.test_team.id,
            'tag_ids': [Command.link(tags[1].id)],
            'stage_id': self.stage_done.id,
        })
        self.assertFalse(ticket.user_id, "The tichet should not get assigned if it's created in a folded stage.")
        ticket.write({'tag_ids': [Command.link(tags[0].id)]})
        self.assertFalse(ticket.user_id, "The ticket should still not get assigned if the tag is added while it's in a folded stage.")

        # Same tests but with SET command
        ticket = self.env['helpdesk.ticket'].create({
            'name': "Test Ticket",
            'team_id': self.test_team.id,
            'tag_ids': [Command.set((tags[0] + tags[1]).ids)],
        })
        self.assertIn(ticket.user_id, self.helpdesk_user + self.helpdesk_manager, "The ticket should be assigned to one of the users of the mapping.")

        ticket = self.env['helpdesk.ticket'].create({
            'name': "Test Ticket",
            'team_id': self.test_team.id,
        })
        ticket.tag_ids = tags[1]
        self.assertEqual(ticket.user_id, self.helpdesk_manager)
        ticket.tag_ids = False
        self.assertEqual(ticket.user_id, self.helpdesk_manager, "Removing the tag should have no effect.")

    def test_team_assignation_tags_multiple_teams(self):
        self.test_team.update({'assign_method': 'tags', 'auto_assignment': True})
        other_team = self.env['helpdesk.team'].with_user(self.helpdesk_manager).create({
            'name': "Other Team",
            'assign_method': 'tags',
            'auto_assignment': True,
        }).sudo()
        tags = self.env['helpdesk.tag'].create([{
            'name': f"tag_{i}",
        } for i in range(3)])

        self.env['helpdesk.tag.assignment'].create([{
            'team_id': self.test_team.id,
            'tag_id': tags[0].id,
            'user_ids': [Command.link(self.helpdesk_user.id)],
        }, {
            'team_id': self.test_team.id,
            'tag_id': tags[1].id,
            'user_ids': [Command.link(self.helpdesk_manager.id)],
        }, {
            'team_id': other_team.id,
            'tag_id': tags[1].id,
            'user_ids': [Command.link(self.helpdesk_user.id)],
        }, {
            'team_id': other_team.id,
            'tag_id': tags[2].id,
            'user_ids': [Command.link(self.helpdesk_manager.id)],
        }])

        tickets = self.env['helpdesk.ticket'].create([{
            'name': "Ticket",
            'team_id': team_id,
            'tag_ids': tag_id and [Command.link(tag_id)],
        } for team_id, tag_id in [
            (self.test_team.id, tags[1].id),
            (other_team.id, tags[1].id),
            (other_team.id, tags[2].id),
            (self.test_team.id, False),
        ]])
        self.assertEqual(tickets[0].user_id.id, self.helpdesk_manager.id, "The first ticket should be assigned to the manager.")
        self.assertEqual(tickets[1].user_id.id, self.helpdesk_user.id, "The second ticket should be assigned to the user.")
        self.assertEqual(tickets[2].user_id.id, self.helpdesk_manager.id, "The third ticket should be assigned to the manager.")
        self.assertFalse(tickets[3].user_id.id, "The fourth ticket should remain unassigned.")

        tickets = self.env['helpdesk.ticket'].create([{
            'name': "Ticket",
            'team_id': team_id,
        } for team_id in [self.test_team.id] * 3 + [other_team.id]])
        self.assertFalse(tickets.user_id)
        tickets.write({
            'tag_ids': [Command.link(tags[1].id)],
        })
        for ticket, exepected_user in zip(tickets, [self.helpdesk_manager] * 3 + [self.helpdesk_user]):
            self.assertEqual(ticket.user_id.id, exepected_user.id, f"The ticket should be assigned to {exepected_user.name}.")

        tickets[1:4].user_id = False
        tickets[2].stage_id = self.stage_done
        tickets.write({
            'tag_ids': [Command.link(tags[0].id)],
        })
        self.assertEqual(tickets[0].user_id.id, self.helpdesk_manager.id, "The first ticket should remain assigned to the manager.")
        self.assertEqual(tickets[1].user_id.id, self.helpdesk_user.id, "The second ticket should be assigned to the user.")
        self.assertFalse(tickets[2].user_id.id, "The third ticket should remain unassigned as it is in a closed stage.")
        self.assertFalse(tickets[3].user_id.id, "The fourth ticket should remain unassigned as there is no match in the mapping for the added tag in its team.")

    def test_ticket_sequence_created_from_multi_company(self):
        """
        In this test we ensure that in a multi-company environment, mail sent to helpdesk team
        create a ticket with the right sequence.
        """
        company0 = self.env.company
        company1 = self.env['res.company'].create({'name': 'new_company0'})

        self.env.user.write({
            'company_ids': [(4, company0.id, False), (4, company1.id, False)],
        })

        helpdesk_team_model = self.env['ir.model'].search([('model', '=', 'helpdesk_team')])
        ticket_model = self.env['ir.model'].search([('model', '=', 'helpdesk.ticket')])

        helpdesk_team0 = self.env['helpdesk.team'].create({
            'name': 'helpdesk team 0',
            'company_id': company0.id,
        })
        helpdesk_team1 = self.env['helpdesk.team'].create({
            'name': 'helpdesk team 1',
            'company_id': company1.id,
        })

        _mail_alias_0, mail_alias_1 = self.env['mail.alias'].create([
            {
                'alias_name': 'helpdesk_team_0',
                'alias_model_id': ticket_model.id,
                'alias_parent_model_id': helpdesk_team_model.id,
                'alias_parent_thread_id': helpdesk_team0.id,
                'alias_defaults': "{'team_id': %s}" % helpdesk_team0.id,
            },
            {
                'alias_name': 'helpdesk_team_1',
                'alias_model_id': ticket_model.id,
                'alias_parent_model_id': helpdesk_team_model.id,
                'alias_parent_thread_id': helpdesk_team1.id,
                'alias_defaults': "{'team_id': %s}" % helpdesk_team1.id,
            }
        ])

        new_message1 = f"""MIME-Version: 1.0
Date: Thu, 27 Dec 2018 16:27:45 +0100
Message-ID: blablabla1
Subject: helpdesk team 1 in company 1
From:  B client <client_b@someprovider.com>
To: {mail_alias_1.display_name}
Content-Type: multipart/alternative; boundary="000000000000a47519057e029630"

--000000000000a47519057e029630
Content-Type: text/plain; charset="UTF-8"


--000000000000a47519057e029630
Content-Type: text/html; charset="UTF-8"
Content-Transfer-Encoding: quoted-printable

<div>A good message bis</div>

--000000000000a47519057e029630--
"""
        self.env['ir.sequence'].create([
            {
                'company_id': company0.id,
                'name': 'test-sequence-00',
                'prefix': 'FirstCompany',
                'code': 'helpdesk.ticket'
            },
            {
                'company_id': company1.id,
                'name': 'test-sequence-01',
                'prefix': 'SecondCompany',
                'code': 'helpdesk.ticket'
            }
        ])

        helpdesk_ticket1_id = self.env['mail.thread'].message_process('helpdesk.ticket', new_message1)
        helpdesk_ticket1 = self.env['helpdesk.ticket'].browse(helpdesk_ticket1_id)
        self.assertTrue(helpdesk_ticket1.ticket_ref.startswith('SecondCompany'))

    def test_email_non_ascii(self):
        """
        Ensure that non-ascii characters are correctly handled in partner email addresses
        """
        new_message = """MIME-Version: 1.0
Date: Thu, 27 Dec 2018 16:27:45 +0100
Message-ID: blablabla1
Subject: helpdesk team 1 in company 1
From:  Client with a §tràÑge name <client_b@someprovaîdère.com>
To: helpdesk_team@test.mycompany.com
Content-Type: multipart/alternative; boundary="000000000000a47519057e029630"

--000000000000a47519057e029630
Content-Type: text/plain; charset="UTF-8"


--000000000000a47519057e029630
Content-Type: text/html; charset="UTF-8"
Content-Transfer-Encoding: quoted-printable

<div>A good message ter</div>

--000000000000a47519057e029630--
"""
        helpdesk_ticket = self.env['mail.thread'].message_process('helpdesk.ticket', new_message)
        helpdesk_ticket = self.env['helpdesk.ticket'].browse(helpdesk_ticket)

        self.assertEqual(helpdesk_ticket.partner_id.name, "Client with a §tràÑge name")
        self.assertEqual(helpdesk_ticket.partner_id.email, "client_b@someprovaîdère.com")
        self.assertEqual(helpdesk_ticket.partner_email, "client_b@someprovaîdère.com")

    def test_team_assignation_balanced_sla(self):
        #We create an sla policy with minimum priority set as '2'
        self.test_team.use_sla = True
        sla = self.env['helpdesk.sla'].create({
            'name': 'test sla policy',
            'team_id': self.test_team.id,
            'stage_id': self.stage_progress.id,
            'priority': '2',
            'time': 1,
        })

        #We create a ticket with priority less than what's on the sla policy
        ticket_1 = self.env['helpdesk.ticket'].create({
            'name': 'test ',
            'team_id': self.test_team.id,
            'priority': '1'
        })

        #We create a ticket with priority equal to what's on the sla policy
        ticket_2 = self.env['helpdesk.ticket'].create({
            'name': 'test sla ticket',
            'team_id': self.test_team.id,
            'priority': '2'
        })

        #We create a ticket with priority greater than what's on the sla policy
        ticket_3 = self.env['helpdesk.ticket'].create({
            'name': 'test sla ticket',
            'team_id': self.test_team.id,
            'priority': '3'
        })
        #We confirm that the sla policy has been applied successfully on the ticket.
        #sla policy must not be applied
        self.assertTrue(sla not in ticket_1.sla_status_ids.mapped('sla_id'))
        self.assertTrue(sla not in ticket_3.sla_status_ids.mapped('sla_id'))
        #sla policy must be applied
        self.assertTrue(sla in ticket_2.sla_status_ids.mapped('sla_id'))

    def test_automatic_ticket_closing(self):
        self.test_team.write({
            'auto_close_ticket': True,
            'auto_close_day': 7,
            'to_stage_id': self.stage_cancel.id,
        })

        create_ticket = lambda stage_id: self.env['helpdesk.ticket'].create({
            'name': 'Ticket 1',
            'team_id': self.test_team.id,
            'stage_id': stage_id,
        })

        ticket_1 = create_ticket(self.stage_new.id)
        ticket_2 = create_ticket(self.stage_progress.id)
        ticket_3 = create_ticket(self.stage_done.id)

        with freeze_time(datetime.now() + relativedelta(days=10)):
            self.test_team._cron_auto_close_tickets()

        # With no from_stage_ids, all tickets from non closing stages should be moved
        self.assertEqual(ticket_1.stage_id, self.stage_cancel)
        self.assertEqual(ticket_2.stage_id, self.stage_cancel)
        self.assertEqual(ticket_3.stage_id, self.stage_done)

        self.test_team.from_stage_ids |= self.stage_progress
        ticket_4 = create_ticket(self.stage_new.id)
        ticket_5 = create_ticket(self.stage_progress.id)
        ticket_6 = create_ticket(self.stage_done.id)

        with freeze_time(datetime.now() + relativedelta(days=10)):
            self.test_team._cron_auto_close_tickets()

        # Only tasks in the stages in from_stage_ids should be moved
        self.assertEqual(ticket_4.stage_id, self.stage_new)
        self.assertEqual(ticket_5.stage_id, self.stage_cancel)
        self.assertEqual(ticket_6.stage_id, self.stage_done)

        ticket_7 = create_ticket(self.stage_progress.id)

        with freeze_time(datetime.now() + relativedelta(days=5)):
            self.test_team._cron_auto_close_tickets()

        # Tickets under the threshold should not be moved (5 < 7)
        self.assertEqual(ticket_7.stage_id, self.stage_progress)

    def test_create_from_email(self):
        with freeze_time('2018-12-27 00:00:00'):
            helpdesk_ticket = self.env['helpdesk.ticket'].create({'name': 'Hi! How was your day?'})

        customer_partner = self.env['res.partner'].create({'name': 'Luc Mélanchetout'})
        helpdesk_partner = self.helpdesk_user.partner_id

        # hours utc to fit in 08:00 - 17:00 belgian calendar
        hours_and_authors = [
            ('08', customer_partner),
            ('09', helpdesk_partner),   #   2h since creation (= first_response_hours)
            ('10', helpdesk_partner),
            ('11', customer_partner),
            ('12', customer_partner),
            ('14', helpdesk_partner),   # + 2h since last customer's message (3h - 1h break)
            ('15', customer_partner),
            ('16', helpdesk_partner),   # + 1h since last customer's message
        ]                               # -----
                                        # = 5h /3responses = 1.67h /response (= avg_response_hours)
        comment_subtype = self.env.ref('mail.mt_comment')
        email_vals = {
            'model': 'helpdesk.ticket',
            'res_id': helpdesk_ticket.id,
            'body': 'Good, you?',
            'subtype_id': comment_subtype.id,
        }
        email_vals_list = []
        for hour, author in hours_and_authors:
            temp_email_vals = email_vals.copy()
            temp_email_vals.update({
                'author_id': author.id,
                'date': '2018-12-27 %s:00:00' % hour,
            })
            email_vals_list.append(temp_email_vals)
        helpdesk_ticket.website_message_ids = self.env['mail.message'].create(email_vals_list)
        self.assertEqual(helpdesk_ticket.first_response_hours, 2.0)
        self.assertEqual(helpdesk_ticket.avg_response_hours, 5 / 3)

    def test_ticket_count_according_to_partner(self):
        # 1) create a partner
        partner = self.env['res.partner'].create({
            'name': 'Freddy Krueger'
        })

        # 2) create one open and one closed ticket
        open_ticket, closed_ticket = self.env['helpdesk.ticket'].with_user(self.helpdesk_user).create([{
            'name': 'open ticket',
            'team_id': self.test_team.id,
            'partner_id': partner.id,
        }, {
            'name': 'solved ticket',
            'team_id': self.test_team.id,
            'partner_id': partner.id,
            'stage_id': self.stage_done.id,
        }])

        # 3) check ticket count according to partner ticket
        self.assertEqual(open_ticket.partner_open_ticket_count, 0, "There should be no other open ticket than this one for this partner")
        self.assertEqual(open_ticket.partner_ticket_count, 1, "There should be one other ticket than this one for this partner")
        self.assertEqual(closed_ticket.partner_open_ticket_count, 1, "There should be one other open ticket than this one for this partner")
        self.assertEqual(closed_ticket.partner_ticket_count, 1, "There should be one other ticket than this one for this partner")

    def test_create_ticket_in_batch_with_email_cc(self):
        user_a, user_b, user_c = self.env['res.users'].create([{
            'name': 'user A',
            'login': 'loginA',
            'email': 'email@bisous1',
        }, {
            'name': 'user B',
            'login': 'loginB',
            'email': 'email@bisous2',
        }, {
            'name': 'user C',
            'login': 'loginC',
            'email': 'email@bisous3',
        }])
        partner_a, partner_b = self.env['res.partner'].create([{
            'name': 'partner A',
            'email': 'email@bisous4',
        }, {
            'name': 'partner B',
        }])
        ticket_1, ticket_2 = self.env['helpdesk.ticket'].with_context({'mail_create_nolog': True}).create([{
            'name': 'ticket 1',
            'team_id': self.test_team.id,
            'email_cc': 'email@bisous1, email@bisous2, email@bisous4',
            'partner_id': partner_b.id,
        }, {
            'name': 'ticket 2',
            'team_id': self.test_team.id,
            'email_cc': 'email@bisous3, email@bisous2, email@bisous4'
        }])
        self.assertTrue(user_a.partner_id in ticket_1.message_partner_ids)
        self.assertTrue(user_b.partner_id in ticket_1.message_partner_ids)
        self.assertFalse(user_c.partner_id in ticket_1.message_partner_ids)
        self.assertFalse(partner_a in ticket_1.message_partner_ids)
        self.assertTrue(partner_b in ticket_1.message_partner_ids)
        self.assertFalse(user_a.partner_id in ticket_2.message_partner_ids)
        self.assertTrue(user_b.partner_id in ticket_2.message_partner_ids)
        self.assertTrue(user_c.partner_id in ticket_2.message_partner_ids)
        self.assertFalse(partner_a in ticket_2.message_partner_ids)
        self.assertFalse(partner_b in ticket_2.message_partner_ids)

    @users('hm')
    def test_mail_alias_after_helpdesk_team_creation(self):
        team_1, team_2, team_3 = self.env['helpdesk.team'].with_context({'mail_create_nolog': True}).create([
            {'name': 'Telecom Team', 'use_alias': True},
            {'name': 'telecom', 'use_alias': True},
            {'name': 'Telecom Team', 'use_alias': True},
        ])
        for team in (team_1, team_2, team_3):
            self.assertTrue(team.alias_id, 'Alias should be created')
            self.assertTrue(team.use_alias, 'Alias feature should be enabled')

        self.assertEqual(team_1.alias_id.alias_name, 'telecom-team', 'Alias name should be telecom-team')
        self.assertEqual(team_2.alias_id.alias_name, 'telecom', 'Alias name should be telecom')
        self.assertEqual(team_3.alias_id.alias_name, 'telecom-team-2', 'Alias name should be telecom-team-2')

    @users('hm')
    def test_helpdesk_team_members_fallback(self):
        helpdesk_form = Form(self.env['helpdesk.team'])
        helpdesk_form.name = 'test team 2'
        helpdesk_form.auto_assignment = True
        helpdesk_form.member_ids.clear()
        helpdesk_form.auto_assignment = False
        helpdesk = helpdesk_form.save()

        self.assertEqual(helpdesk.member_ids, self.env.user)

    def test_create_from_internal_for_internal(self):
        """
        Test that we can create a ticket from an internal user for an internal user, without raising any access error.
        Also test that empty phone number doesn't overwrite the partner's phone number.
        """
        user = self.env['res.users'].create({
            'name': 'User',
            'login': 'user',
            'email': 'user@user.com',
            'group_ids': [(6, 0, [self.env.ref('helpdesk.group_helpdesk_manager').id,
                        self.env.ref('base.group_partner_manager').id])],
        })

        self.assertFalse(self.helpdesk_user.partner_id.phone)
        ticket = self.env['helpdesk.ticket'].with_user(user).create({
            'name': 'test ticket 1',
            'team_id': self.test_team.id,
            'partner_id': self.helpdesk_user.partner_id.id,
            'partner_phone': '123'
        })
        self.assertEqual(self.helpdesk_user.partner_id.phone, ticket.partner_phone)
        ticket = self.env['helpdesk.ticket'].with_user(self.helpdesk_user).create({
            'name': 'test ticket 2',
            'team_id': self.test_team.id,
            'partner_id': self.helpdesk_user.partner_id.id,
            'partner_phone': ''
        })
        self.assertEqual(self.helpdesk_user.partner_id.phone, '123')

    def test_ticket_display_name(self):
        """
        Test to verify that the display_name should not display the ID of its record when
        it is not yet defined, leading to the display of '#False' in the interface.
        Additionally test the display of partner_name in the display_name when passed in context.

        The ticket is created in cache with the method `new` to allow the display_name
        to be computed with the ticket_id still being `False`.
        """
        ticket = self.env['helpdesk.ticket'].new({
            'name': "test ticket",
            'partner_id': self.partner.id
        })
        self.assertEqual(ticket.display_name, "test ticket")

        # create a record with the values passed from above ticket
        record = self.env['helpdesk.ticket'].create({
            'name': ticket.name,
            'partner_id': ticket.partner_id.id
        })
        # verify that the ticket_ref is now added to the display_name
        self.assertEqual(record.display_name, f"test ticket (#{record.ticket_ref})")

        # create another record with the partner_name in the context
        record_partner = self.env['helpdesk.ticket'].with_context(with_partner=True).create({
            'name': "test ticket with partner",
            'partner_id': self.partner.id
        })
        # verify that the partner_name is now added to the display_name
        self.assertEqual(record_partner.display_name,
                         f"test ticket with partner (#{record_partner.ticket_ref}) - {self.partner.name}")

    def test_helpdesk_team_with_deleted_user(self):
        user = self.env['res.users'].create({
            'name': 'demo user',
            'login': 'login',
        })

        helpdesk_team1 = self.env['helpdesk.team'].create({
            'name': 'helpdesk team1',
            'company_id': self.env.company.id,
            'auto_assignment': True,
            'assign_method': 'randomly',
            'member_ids': [(6, 0, [user.id])],
        })

        helpdesk_team2 = self.env['helpdesk.team'].create({
            'name': 'helpdesk team2',
            'company_id': self.env.company.id,
            'auto_assignment': True,
            'assign_method': 'balanced',
            'member_ids': [(6, 0, [user.id])],
        })

        user.unlink()

        ticket1 = self.env['helpdesk.ticket'].create({
            'name': 'test ticket1',
            'team_id': helpdesk_team1.id,
        })

        ticket2 = self.env['helpdesk.ticket'].create({
            'name': 'test ticket2',
            'team_id': helpdesk_team2.id,
        })

        self.assertFalse(ticket1.user_id)
        self.assertFalse(ticket2.user_id)

    def test_copy_first_and_avg_response_time(self):
        helpdesk_ticket = self.env['helpdesk.ticket'].create({
            'name': 'Test ticket',
            'first_response_hours': '1.5',
            'avg_response_hours': '2.33',
            'total_response_hours': '4.5',
        })

        ticket_copy = helpdesk_ticket.copy()
        self.assertEqual(ticket_copy.first_response_hours, 0.0)
        self.assertEqual(ticket_copy.avg_response_hours, 0.0)
        self.assertEqual(ticket_copy.total_response_hours, 0.0)

    def test_copy_ticket_without_archive_user(self):
        tickets = self.env['helpdesk.ticket'].create([
            {
                'name': "Ticket A",
                'team_id': self.test_team.id,
                'user_id': self.helpdesk_user.id,
            }, {
                'name': "Ticket B",
                'team_id': self.test_team.id,
                'user_id': self.helpdesk_manager.id,
            },
        ])
        self.helpdesk_user.action_archive()
        ticket_a, ticket_b = tickets.copy()
        self.assertFalse(ticket_a.user_id, "Archived user should not be assigned to the new ticket.")
        self.assertEqual(ticket_b.user_id, self.helpdesk_manager)

        # exception if the user gives the archived user in the default parameter
        ticket2_a, ticket2_b = tickets.copy({'user_id': self.helpdesk_user.id})
        self.assertEqual(ticket2_a.user_id, self.helpdesk_user)
        self.assertEqual(ticket2_b.user_id, self.helpdesk_user)

    def test_assigned_customer_multicompany(self):
        """
        Test in multicompany that the assigned customer is in the same company as the ticket

        Test Case:
        ==========
        1. Create 2 companies
        2. Create `res.partner` `test_partner` in company1
        3. Create ticket for helpdesk_team2 from company2
           with email of `test_partner`
        4. Check that the partner on the ticket is a newly
           created partner in company2 and different from `test_partner`
        """

        company1 = self.main_company_id
        company2, company3 = self.env['res.company'].create([
            {'name': 'company2'},
            {'name': 'company3'},
        ])

        # Create a partner in company1
        test_partner, test_partner2 = self.env['res.partner'].create([
            {
                'name': 'test partner',
                'email': 'testmail@test.com',
                'company_id': company1,
            }, {
                'name': 'test partner without company',
                'email': 'testcompany@test.com',
                'company_type': 'company',
                'company_id': False,
            },
        ])

        # Create a helpdesk team in company2
        helpdesk_team, helpdesk_team_company3 = self.env['helpdesk.team'].create([
            {'name': 'test team', 'company_id': company2.id},
            {'name': 'test team2', 'company_id': company3.id},
        ])

        # Create a ticket in company2 with email of test_partner
        ticket = self.env['helpdesk.ticket'].create({
            'partner_name': 'Test Name',
            'partner_email': 'testmail@test.com',
            'name': 'Ticket Name',
            'team_id': helpdesk_team.id,
        })

        self.assertTrue(ticket.partner_id)
        self.assertNotEqual(ticket.partner_id, test_partner)
        self.assertEqual(ticket.partner_id.company_id, ticket.company_id)

        ticket2 = self.env['helpdesk.ticket'].create({
            'partner_name': 'Test Name',
            'partner_email': 'testcompany@test.com',
            'name': 'Ticket Name',
            'team_id': helpdesk_team_company3.id,
        })

        self.assertEqual(ticket2.partner_id, test_partner2)
        self.assertFalse(ticket2.partner_id.company_id)

    def test_ticket_created_in_closed_stage_sets_close_date(self):
        """Test that a ticket created directly in a folded (closed) stage sets close_date."""
        with self._ticket_patch_now("2024-06-01 10:00:00"):
            ticket = self.env['helpdesk.ticket'].create({
                'name': 'Closed from start',
                'team_id': self.test_team.id,
                'stage_id': self.stage_done.id,
            })
        self.assertEqual(
            ticket.close_date,
            datetime(2024, 6, 1, 10, 0, 0),
            "Ticket created in a closed stage should have close_date set to the current datetime"
        )

    def test_save_ticket_without_tags(self):
        self.test_team.update({'assign_method': 'tags', 'auto_assignment': True})

        tag = self.env['helpdesk.tag'].create({'name': 'Test Tag'})

        ticket = self.env['helpdesk.ticket'].create({
            'name': 'Test Ticket',
            'team_id': self.test_team.id,
            'tag_ids': [(6, 0, [tag.id])],
        })
        self.assertIn(tag, ticket.tag_ids)

        ticket.write({'tag_ids': [(5, 0, 0)]})
        self.assertFalse(ticket.tag_ids)

    def test_create_ticket_with_stage_days_to_rot(self):
        """Test that creating a ticket with stage New having Days to rot > 0"""
        self.stage_new.rotting_threshold_days = 1
        ticket_form = Form(self.env['helpdesk.ticket'])
        ticket_form.name = "Test Ticket"
        ticket = ticket_form.save()
        self.assertTrue(ticket.id)
        self.assertEqual(ticket.stage_id.name, 'New')
