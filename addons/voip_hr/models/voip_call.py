from odoo import api, models


class VoipCall(models.Model):
    _inherit = "voip.call"

    @api.depends("partner_id.employee_ids.company_id", "user_id.partner_id.employee_ids.company_id")
    def _compute_is_within_same_company(self):
        def participants_have_same_employee_company(call):
            return bool(
                set(call.partner_id.employee_ids.company_id.ids)
                & set(call.user_id.partner_id.employee_ids.company_id.ids),
            )

        internal_calls = self.filtered(participants_have_same_employee_company)
        internal_calls.is_within_same_company = True
        super(VoipCall, self - internal_calls)._compute_is_within_same_company()
