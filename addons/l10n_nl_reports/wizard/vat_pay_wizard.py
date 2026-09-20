from stdnum.nl.btw import validate

from odoo import models, _
from odoo.exceptions import UserError


class VATPayWizard(models.TransientModel):
    _name = 'l10n_nl_reports.vat.pay.wizard'
    _inherit = ['qr.code.payment.wizard']
    _description = "Payment instructions for VAT"

    def _generate_communication(self):
        company = self.return_id.company_id
        periodicity = self.return_id.type_id._get_periodicity(company)
        try:
            nl_vat = company.l10n_nl_reports_sbr_ob_nummer or company.vat
            vat = validate(nl_vat)
        except Exception as e:
            raise UserError(_(
                "Something went wrong while validating the VAT number: %s. You can modify it in the company settings.",
                nl_vat
            )) from e
        head, tail = vat.split("B")
        date = self.return_id.date_from
        period_code_map = {
            'monthly': f'{date.month:02}',
            'trimester': f'{20 + date.month}',
            'year': '40',
        }

        if periodicity not in period_code_map:
            raise UserError(_(
                "Invalid tax periodicity. Please use one of the following: %s.",
                ', '.join(
                    label
                    for value, label in self.return_id.type_id._fields['deadline_periodicity']._description_selection(self.env)
                    if value in period_code_map
                )
            ))

        block_1 = f"{head[:3]}"
        block_2 = f"{head[3:7]}"
        block_3 = f"{head[7:8]}1{str(date.year)[-1]}{tail[0]}"
        block_4 = f"{tail[1]}{period_code_map[periodicity]}0"
        blocks = [block_1, block_2, block_3, block_4]

        checksum = self._l10n_nl_get_modulo_11_checksum("".join(blocks))
        return checksum + ".".join(blocks)

    def _l10n_nl_get_modulo_11_checksum(self, number):
        """
        Calculates the Modulo 11 checksum for a given numeric string using a predefined set of weights.

        The function iterates over each digit in the input string from right to left, applying the corresponding weight
        in a cyclic manner. The checksum is computed as the weighted sum of the digits modulo 11.

        Source: https://www.betaalvereniging.nl/betalingsverkeer/giraal-betalingsverkeer/betalingskenmerken/specificaties-nl-betalingskenmerk/

        :param str number: A string representing a numeric input for which the checksum needs to be calculated.
        :returns: The Modulo 11 checksum as a string.
            Returns '0' or '1' if the remainder is 0 or 1,
            otherwise returns the complement of the remainder (i.e., 11 - remainder).
        :rtype: str.
        """
        n = len(number)
        weights = [2, 4, 8, 5, 10, 9, 7, 3, 6, 1]
        remainder = sum(int(number[n - i - 1]) * weights[i % len(weights)] for i in range(n)) % 11

        if remainder in (0, 1):
            return str(remainder)

        return str(11 - remainder)

    def action_send_email_instructions(self):
        self.ensure_one()
        template = self.env.ref('l10n_nl_reports.email_template_vat_payment_instructions', raise_if_not_found=False)
        return self.return_id.action_send_email_instructions(self, template)
