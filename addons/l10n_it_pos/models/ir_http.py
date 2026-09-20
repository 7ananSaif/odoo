from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        res = super().session_info()
        for company in self.env.user.company_ids:
            res["user_companies"]["allowed_companies"][company.id]["country_code"] = company.country_id.code
        return res
