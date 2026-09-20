from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools import format_list


class AccountAccount(models.Model):
    _inherit = 'account.account'

    @property
    def ESG_VALID_ACCOUNT_TYPES(self):
        return ('expense', 'expense_other', 'expense_direct_cost', 'asset_fixed')

    @property
    def ESG_VALID_ACCOUNT_TYPE_NAMES(self):
        return [name for key, name in dict(self._fields['account_type']._description_selection(self.env)).items() if key in self.ESG_VALID_ACCOUNT_TYPES]

    @api.onchange('account_type')
    def _onchange_account_type(self):
        if (
            self._origin.account_type in self.ESG_VALID_ACCOUNT_TYPES
            and self.account_type not in self.ESG_VALID_ACCOUNT_TYPES
            and bool(
                self.sudo()._fetch_esg_assignation_lines_linked_to_account(limit=1)
                or self.sudo()._fetch_esg_account_move_lines_linked_to_account(limit=1)
            )
        ):
            return {
                'warning': {
                    'title': self.env._('Warning'),
                    'message': self.env._(
                        'Changing the account type to anything other than %(valid_account_type_names)s will reset all emission factors linked to journal items using this account.\n'
                        'In addition, it will remove all the ESG assignations lines linked to that account.\n'
                        'Are you sure you want to continue?',
                        valid_account_type_names=format_list(self.env, self.ESG_VALID_ACCOUNT_TYPE_NAMES, 'or'),
                    ),
                },
            }

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('from_emission_factor_line'):
            for vals in vals_list:
                if vals.get('account_type') not in self.ESG_VALID_ACCOUNT_TYPES:
                    raise UserError(self.env._(
                        'You can only create accounts of type %(valid_account_type_names)s in the ESG module, as emission factors can only be linked to expense or asset accounts.',
                        valid_account_type_names=format_list(self.env, self.ESG_VALID_ACCOUNT_TYPE_NAMES, 'or'),
                    ))
        return super().create(vals_list)

    def write(self, vals):
        if (
            'account_type' in vals
            and vals.get('account_type') not in self.ESG_VALID_ACCOUNT_TYPES
            and (valid_accounts := self.filtered(lambda account: account.account_type in self.ESG_VALID_ACCOUNT_TYPES))
        ):
            valid_accounts.sudo()._fetch_esg_assignation_lines_linked_to_account().unlink()
            valid_accounts.sudo()._fetch_esg_account_move_lines_linked_to_account().esg_emission_factor_id = False
        return super().write(vals)

    def _fetch_esg_assignation_lines_linked_to_account(self, limit=None):
        return self.env['esg.assignation.line'].search(domain=[('account_id', 'in', self.ids)], limit=limit)

    def _fetch_esg_account_move_lines_linked_to_account(self, limit=None):
        return self.env['account.move.line'].search(
            domain=[
                ('account_id', 'in', self.ids),
                ('esg_emission_factor_id', '!=', False),
            ], limit=limit
        )
