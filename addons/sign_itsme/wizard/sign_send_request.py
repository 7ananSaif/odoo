from odoo import api, models


class SignSendRequest(models.TransientModel):
    _inherit = "sign.send.request"

    @api.depends("only_autofill_readonly", "signers_count", "is_user_signer")
    def _compute_display_download_button(self):
        # The condition for showing the download button is that there is only 1 signer AND
        # that the user is the signer AND that the signer is not using itsme AND that everything is autofillable.
        # What is written here is like breaking up that requirement into
        # (first signer not using itsme) AND (only 1 signer AND user is signer AND all autofillable)
        # The second parenthesis is ensured by super()._compute_display_download_button()
        for wiz in self:
            if wiz.signer_ids[:1].role_id.auth_method == "itsme":
                wiz.display_download_button = False
            else:
                super()._compute_display_download_button()
