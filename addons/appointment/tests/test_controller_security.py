from itertools import product
from werkzeug.urls import url_encode

from odoo import http
from odoo.tests import tagged

from .test_appointment_ui import AppointmentUICommon


@tagged("appointment_ui", "security", "-at_install", "post_install")
class AppointmentControllerSecurity(AppointmentUICommon):
    def test_appointment_submit_no_csrf(self):
        """Check that the form does not require a CSRF token when logged out.

        When logged out we should always create a new partner regardless of whether one exists
        with similar contact info, so it is ok to not check CSRF as we do not use any session-related
        information during form submission.
        """
        invite = self.env["appointment.invite"].create({
            "appointment_type_ids": self.apt_type_bxls_2days.ids,
            "resources_choice": "all_assigned_resources",
        })
        appointment_url = (
            f"/appointment/{self.apt_type_bxls_2days.id}/submit?{url_encode(invite._get_redirect_url_parameters())}"
        )
        phone_question = self.apt_type_bxls_2days._get_main_phone_question()
        self.assertTrue(phone_question)

        base_appointment_data = {
            "allday": 0,
            "csrf_token": False,
            "duration_str": "1.0",
            "datetime_str": "2022-07-04 12:30:00",
            "email": self.apt_manager.email,
            "name": "logged-out Apt Manager",
            f"question_{phone_question.id}": self.apt_manager.phone,
            "staff_user_id": self.staff_user_bxls.id,
        }
        existing_partners = self.staff_user_bxls.partner_id + self.apt_manager.partner_id
        for login, with_csrf in product((None, self.apt_manager.login), (False, True)):
            with self.subTest(login=login, with_csrf=with_csrf):
                self.authenticate(login, login)
                res = self.url_open(
                    appointment_url,
                    data=base_appointment_data | ({"csrf_token": http.Request.csrf_token(self)} if with_csrf else {}),
                )

                if not login or with_csrf:
                    self.assertTrue(res.ok)
                    self.assertIn("/calendar/view/", res.url)
                else:
                    self.assertFalse(res.ok)
                    continue

                latest_partner = self.env["res.partner"].search([], order="id DESC", limit=1)
                latest_appointment = self.env["calendar.event"].search([], order="id DESC", limit=1)

                if not login:
                    self.assertNotIn(latest_partner, existing_partners)

                    self.assertEqual(latest_partner.email, self.apt_manager.email)
                    self.assertEqual(latest_partner.name, "logged-out Apt Manager")
                    self.assertEqual(latest_appointment.partner_ids, latest_partner + self.staff_user_bxls.partner_id)
                    self.assertNotEqual(latest_partner, self.apt_manager.partner_id)
                elif login and with_csrf:
                    self.assertEqual(
                        latest_appointment.partner_ids, self.apt_manager.partner_id + self.staff_user_bxls.partner_id
                    )
                existing_partners |= latest_partner
                # avoid using up a slot for following tests
                latest_appointment.unlink()
