# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class SignSendRequest(models.TransientModel):
    _inherit = "sign.send.request"

    def _get_default_signer(self):
        reference_doc = self.env.context.get("default_reference_doc")
        if reference_doc:
            model, id = reference_doc.split(',')
            if model == "hr.applicant":
                return self.env["hr.applicant"].browse(int(id)).partner_id
        return super()._get_default_signer()
