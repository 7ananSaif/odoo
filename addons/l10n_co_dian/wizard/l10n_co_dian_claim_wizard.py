from odoo import api, models, fields


class L10nCODianClaimWizard(models.TransientModel):
    _name = 'l10n_co_dian.claim.wizard'
    _description = "Wizard used for choosing a reason for rejecting a Vendor bill"

    @api.model
    def _claim_reason_selection(self):
        return self.env['account.move']._fields['l10n_co_dian_claim_reason']._description_selection(self.env)

    claim_reason = fields.Selection(string="Rejection Reason", selection=_claim_reason_selection, required=True)

    def button_claim(self):
        move_id = self.env.context.get('move_id', False)

        if move_id:
            move = self.env['account.move'].browse(move_id)
            move.l10n_co_dian_claim_reason = self.claim_reason
            move.l10n_co_dian_send_event_update_status_claimed()
