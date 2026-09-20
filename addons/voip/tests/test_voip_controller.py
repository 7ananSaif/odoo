from http import HTTPStatus

from odoo import http
from odoo.tests import tagged
from odoo.tests.common import HttpCase, new_test_user


@tagged("-at_install", "post_install")
class TestVoipController(HttpCase):

    def test_recording_can_only_be_uploaded_by_owner_of_the_call(self):
        rightful_record_owner = new_test_user(self.env, login="based VoIP user 😤")
        call = self.env["voip.call"].create({
            "phone_number": "0491 577 644",
            "user_id": rightful_record_owner.id,
        })
        evil_uploader = new_test_user(self.env, login="evil uploader 👺")

        self.authenticate(evil_uploader.login, evil_uploader.password)
        response = self.url_open(
            f"/voip/upload_recording/{call.id}",
            data={"csrf_token": http.Request.csrf_token(self)},
            files={"ufile": ("recording.ogg", b"OggS", "audio/ogg")},
            method="POST",
        )
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

        self.authenticate(rightful_record_owner.login, rightful_record_owner.password)
        response = self.url_open(
            f"/voip/upload_recording/{call.id}",
            data={"csrf_token": http.Request.csrf_token(self)},
            files={"ufile": ("recording.ogg", b"OggS", "audio/ogg")},
            method="POST",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
