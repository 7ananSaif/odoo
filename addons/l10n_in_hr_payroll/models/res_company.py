# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_in_epf_employer_id = fields.Char(string="EPF Employer ID",
        help="Region code: 2 uppercase letters (e.g., 'GJ' for Gujarat)\nOffice code: 3 uppercase letters\
        (e.g., 'AHM' for Ahmedabad)\nEstablishment code: 1 to 7 digits (e.g., '1234567')\nExtension code:\
        3 digits (e.g., '000')\nAccount number: 1 to 7 digits (e.g., '1234567')\nFormat: XX/XXX/1234567/000/1234567")
    l10n_in_esic_ip_number = fields.Char(string="ESIC IP Number",
        help="Code of 17 digits.\n The Identification number is assigned to the company if registered under the\
        Indian provisions of the Employee\'s State Insurance (ESI) Act.")
    l10n_in_pt_number = fields.Char(string="PT Number",
        help="The PTN digit number with the first two digits indicating the State.")
    l10n_in_provident_fund = fields.Boolean(string="Provident Fund",
        help="Check this box if the company is required to comply with the Indian provisions of the\
        Employee's Provident Fund (EPF) Act.")
    l10n_in_esic = fields.Boolean(string="Employee's State Insurance",
        help="Check this box if the company is required to comply with the Indian provisions of the\
        Employee's State Insurance (ESI) Act.")
    l10n_in_pt = fields.Boolean(string="Professional Tax(PT)")
    l10n_in_labour_welfare = fields.Boolean(string="Labour Welfare Fund",
        help="Check this box if the company is required to comply with the Indian provisions of the Labour\
        Welfare Fund (LWF) Act.")
    l10n_in_labour_identification_number = fields.Char(string="Labour Identification Number",
        help="The Labour Welfare Fund ID is assigned to the company if registered under the\
        Indian provisions of the Labour Welfare Fund (LWF) Act.")
    _check_l10n_in_epf_employer_id = models.Constraint(
        "CHECK (l10n_in_epf_employer_id ~ '^[A-Z]{2}/[A-Z]{3}/[0-9]{1,7}/[0-9]{3}/[0-9]{1,7}$')",
        "EPF Number format must be: XX/XXX/1234567/000/1234567"
    )
    _check_l10n_in_esic_ip_number = models.Constraint(
        "CHECK(l10n_in_esic_ip_number ~ '^[0-9]{17}$')",
        'ESIC IP Number must be exactly 17 characters.'
    )
