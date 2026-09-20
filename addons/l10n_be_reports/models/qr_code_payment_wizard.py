from odoo import models
from odoo.exceptions import ValidationError


class QRCodePaymentWizard(models.TransientModel):
    _inherit = 'qr.code.payment.wizard'

    @staticmethod
    def _be_company_vat_communication(company):
        ''' Taken from https://finances.belgium.be/fr/communication-structuree
        '''
        try:
            vat, country_code = company.partner_id._run_vat_checks(
                company.account_fiscal_country_id,
                company.vat,
            )
        except ValidationError:
            return ""
        if country_code != 'BE' or company.account_fiscal_country_id.code != 'BE':
            return ""
        vat = vat.upper().removeprefix('BE')
        number = int(vat)
        suffix = f"{number % 97 or 97:02}"
        return f"+++{vat[:3]}/{vat[3:7]}/{vat[7:]}{suffix}+++"
