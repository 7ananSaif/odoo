# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import Form
from .sign_request_common import SignRequestCommon


class TestSignWizard(SignRequestCommon):

    def test_sign_wizard_access_signature_of_other_user(self):
        self.template_2_roles.sign_item_ids[1].type_id = self.ref('sign.sign_item_type_signature')
        self.template_2_roles.authorized_ids += self.user_1
        form = Form(self.env['sign.send.request'].with_user(self.user_1).with_context(default_template_id=self.template_2_roles.id))
        wizard = form.save()
        self.assertFalse(wizard.display_download_button)
        self.template_2_roles.sign_item_ids[1].type_id = self.ref('sign.sign_item_type_initial')
        Form(self.env['sign.send.request'].with_user(self.user_1).with_context(default_template_id=self.template_2_roles.id))
        wizard = form.save()
        self.assertFalse(wizard.display_download_button)
