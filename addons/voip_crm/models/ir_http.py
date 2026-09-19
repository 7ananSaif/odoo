from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        res = super().session_info()
        res["groups"]["sales_team.group_sale_salesman"] = self.env.user.has_group("sales_team.group_sale_salesman")
        res["groups"]["sales_team.group_sale_manager"] = self.env.user.has_group("sales_team.group_sale_manager")
        return res
