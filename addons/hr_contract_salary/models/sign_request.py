from odoo import models, _


class SignRequest(models.Model):
    _inherit = 'sign.request'

    def cancel(self):
        super().cancel()
        # sudo(), as not everyone has access to 'hr.contract.salary.offer'
        # but they should be able to cancel their sign request
        offers_sudo = self.env['hr.contract.salary.offer'].sudo().search([('sign_request_ids', 'in', self.ids)])
        offers_sudo.applicant_id.unlink_archived_versions()
        offers_sudo.write({'state': 'cancelled'})
        for offer in offers_sudo:
            offer.message_post(body=_("The offer has been cancelled due to the signature request cancellation."))
