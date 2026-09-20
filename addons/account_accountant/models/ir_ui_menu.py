# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _get_account_readonly_menu_ids(self):
        """
        Returns a list of xmlids to hide if the user does not have the `group_account_readonly` group.
        """
        return [
            'account_accountant.account_tag_menu',
            'account_accountant.menu_account_group',
        ]

    def _visible_menu_ids(self, debug=False):
        visible_ids = super()._visible_menu_ids(debug)
        # These menus should only be visible to accountants (users with group_account_readonly) and the group specified on the menu
        # We want to avoid moving these menus to the new `accountant` module
        if not self.env.user.has_group('account.group_account_readonly'):
            accounting_menus = self._get_account_readonly_menu_ids()
            hidden_menu_ids = {
                menu_id for ref_menu in accounting_menus
                if (menu_id := self.env['ir.model.data']._xmlid_to_res_id(ref_menu))
            }
            return visible_ids - hidden_menu_ids
        return visible_ids
