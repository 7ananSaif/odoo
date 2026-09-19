from odoo import Command, _, api, models
from odoo.exceptions import RedirectWarning, UserError

import json
import re

from math import copysign


class AccountReconcileModelLine(models.Model):
    _inherit = 'account.reconcile.model.line'

    def _prepare_aml_vals(self, partner):
        """ Prepare a dictionary that will be used later to create a new journal item (account.move.line) for the
        given reconcile model line.

        :param partner: The partner to be linked to the journal item.
        :return:        A python dictionary.
        """
        self.ensure_one()

        taxes = self.tax_ids or self.account_id.tax_ids
        if taxes and partner:
            fiscal_position = self.env['account.fiscal.position']._get_fiscal_position(partner)
            if fiscal_position:
                taxes = fiscal_position.map_tax(taxes)

        values = {
            'name': self.label,
            'partner_id': partner.id,
            'analytic_distribution': self.analytic_distribution,
            'reconcile_model_id': self.model_id.id,
        }
        if taxes:
            values['tax_ids'] = [Command.set(taxes.ids)]
        if self.account_id:
            values['account_id'] = self.account_id.id
        return values

    def _apply_in_manual_widget(self, residual_amount_currency, residual_balance, partner, st_line):
        """ Prepare a dictionary that will be used later to create a new journal item (account.move.line) for the
        given reconcile model line used by the manual reconciliation widget.

        :param residual_amount_currency:    The current amount currency expressed in the account's currency.
        :param residual_balance:            The current balance expressed in the company currency.
        :param partner:                     The partner to be linked to the journal item.
        :param st_line:                     The statement line.
        :return:                            A python dictionary.
        """
        self.ensure_one()

        currency = st_line.foreign_currency_id or st_line.journal_id.currency_id or st_line.company_currency_id
        if self.amount_type == 'percentage':
            amount_currency = currency.round(residual_amount_currency * (self.amount / 100.0))
            balance = st_line.company_currency_id.round(residual_balance * (self.amount / 100.0))
        elif self.amount_type == 'fixed':
            sign = 1 if residual_amount_currency > 0.0 else -1
            amount_currency = currency.round(self.amount * sign)
            balance = st_line.company_currency_id.round(self.amount * sign)
        else:
            raise UserError(_("This reconciliation model can't be used in the manual reconciliation widget because its "
                              "configuration is not adapted"))

        return {
            **self._prepare_aml_vals(partner),
            'currency_id': currency.id,
            'balance': balance,
            'amount_currency': amount_currency,
        }

    def _apply_in_bank_widget(self, residual_amount_currency, residual_balance, partner, st_line):
        """ Prepare a dictionary that will be used later to create a new journal item (account.move.line) for the
        given reconcile model line used by the bank reconciliation widget.

        :param residual_amount_currency:    The current amount currency expressed in the statement line's currency.
        :param residual_balance:            The current balance expressed in the company currency.
        :param partner:                     The partner to be linked to the journal item.
        :param st_line:                     The statement line mounted inside the bank reconciliation widget.
        :return:                            A python dictionary.
        """
        self.ensure_one()
        currency = st_line.foreign_currency_id or st_line.journal_id.currency_id or st_line.company_currency_id

        aml_values = {'currency_id': currency.id}

        if self.amount_type == 'percentage_st_line':
            _transaction_amount, _transaction_currency, journal_amount, journal_currency, company_amount, company_currency \
                = st_line._get_accounting_amounts_and_currencies()
            aml_values['amount_currency'] = currency.round(-journal_amount * self.amount / 100.0)
            aml_values['balance'] = company_currency.round(-company_amount * self.amount / 100.0)
            aml_values['currency_id'] = journal_currency.id
        elif self.amount_type == 'regex':
            aml_values['amount_currency'] = self._get_amount_currency_by_regex(st_line, residual_amount_currency, self.amount_string)
            aml_values['balance'] = self._get_amount_currency_by_regex(st_line, residual_balance, self.amount_string)

        if 'amount_currency' not in aml_values or 'balance' not in aml_values:
            aml_values.update(self._apply_in_manual_widget(
                residual_amount_currency=residual_amount_currency,
                residual_balance=residual_balance,
                partner=partner,
                st_line=st_line,
            ))
        else:
            aml_values.update(self._prepare_aml_vals(partner))

        if not aml_values.get('name', False):
            aml_values['name'] = st_line.payment_ref

        return aml_values

    @api.model
    def _get_amount_currency_by_regex(self, st_line, residual_amount_currency, amount_string):
        sign = 1 if residual_amount_currency > 0.0 else -1
        transaction_details = json.dumps(st_line.transaction_details) if st_line.transaction_details else False
        for target_field in (st_line.payment_ref, transaction_details, st_line.narration):
            if not target_field:
                continue
            if match := re.search(amount_string, target_field):
                try:
                    extracted_match_group = re.search(r'\d+[,.]?\d*', match.group(1))
                    extracted_balance = float(extracted_match_group.group().replace(',', '.'))
                    return copysign(extracted_balance * sign, residual_amount_currency)
                except IndexError:         # from .group(1) if the regex doesn't contain a parenthesis part
                    raise RedirectWarning(_("The regular expression for capturing the counterpart amount appears to be incorrectly formatted.\n"
                        "Please make sure that the part of the regex capturing the amount is the first (or only) one in parentheses, for example: BRT: ([\\d,.]+)."),
                        self.model_id._get_records_action(),
                        _("Open reconcile model")
                    )
                except AttributeError:     # from an inconclusive search -> None.group().replace(...)
                    raise RedirectWarning(_("The regular expression for capturing the counterpart amount appears to be incorrectly formatted.\n"
                        "Please make sure that the part of the regex capturing the amount (in parentheses) cannot capture an empty value (usually by an incorrect use of ? or *) "
                        "or any value with no digit. For example: BRT: ([\\d,.]+)."),
                        self.model_id._get_records_action(),
                        _("Open reconcile model")
                    )
        return 0.0
