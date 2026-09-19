# Part of Odoo. See LICENSE file for full copyright and licensing details.
from freezegun import freeze_time

from odoo.exceptions import ValidationError

from .sign_request_common import SignRequestCommon


class TestSignRequestShare(SignRequestCommon):

    def test_shared_sign_request_validity_cannot_be_set_in_the_past(self):
        """ Tests that the sign request cannot be shared when the validity is set in the past. """
        with freeze_time("2025-05-01"):
            with self.assertRaisesRegex(ValidationError, "The sign request validity cannot be set in the past."):
                self.env["sign.request.share"].create({
                    "template_id": self.template_1_role.id,
                    "is_shared": False,
                    "validity": "2025-04-10"
                })

    def test_cannot_create_shared_request_with_more_than_one_role(self):
        """ Tests that the sign request cannot be shared if it is linked to more than one role. """
        with self.assertRaisesRegex(ValidationError, "You cannot share this document by link, because it has fields to be filled by different roles. Use Send button instead."):
            self.env["sign.request.share"].create({
                "template_id": self.template_3_roles.id,
                "is_shared": False,
                "validity": "2025-04-10"
            })
