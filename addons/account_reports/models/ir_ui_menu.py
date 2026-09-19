from odoo import models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _get_account_readonly_menu_ids(self):
        res = super()._get_account_readonly_menu_ids()
        res.extend([
            'account_reports.menu_action_account_report_multicurrency_revaluation',
            'account_reports.menu_action_account_report_tree',
        ])
        return res
