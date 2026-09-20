# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import csv
import io

from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import date_utils


class L10nUsForm940(models.Model):
    _name = 'l10n.us.940'
    _description = 'Form 940'

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "US":
            raise UserError(_('You must be logged in a US company to use this feature'))
        return super().default_get(fields)

    single_state_payer_id = fields.Many2one(
        'res.country.state',
        domain=lambda self: [('country_id', '=', self.env.ref('base.us').id)],
        string="Single State Payer",
        help="Only select if you paid employees in only ONE State."
    )
    is_multi_state_employer = fields.Boolean("Multi State Employer", help="If you had to pay state unemployment tax in more than one state, you are a multi-state employer.")
    has_paid_credit_reduction_state = fields.Boolean("Paid in Credit Reduction State", help='Check if you paid wages in a state that is subject to "Credit Reduction".')
    irs_payment_option = fields.Selection([
        ('efw', 'EFW'),
        ('eftps', 'EFTPS'),
        ('check_money_order', 'Check/Money Order'),
        ('credit_card', 'Credit Card'),
    ], required=True, string="IRS Payment Option", help="""
    Select the payment method you will use to file your form:
    - Electronic Funds Withdrawal (EFW)
    - Electronic Federal Tax Payment System (EFTPS)
    - Check or Money order
    - Credit Card""")
    year = fields.Char(required=True, default=lambda self: fields.Date.today().year, string="Tax Year")
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        domain=lambda self: [('id', 'in', self.env.companies.ids)],
        required=True)
    allowed_payslip_ids = fields.Many2many('hr.payslip', compute='_compute_allowed_payslip_ids')
    payslip_ids = fields.Many2many(
        'hr.payslip',
        compute='_compute_payslips_ids',
        store=True,
        readonly=False,
        domain="[('id', 'in', allowed_payslip_ids)]")
    csv_file = fields.Binary("CSV file", readonly=True)
    csv_filename = fields.Char()

    @api.depends('year')
    def _compute_display_name(self):
        for form_940 in self:
            form_940.display_name = f"Form 940 - {form_940.year}"

    @api.depends('allowed_payslip_ids')
    def _compute_payslips_ids(self):
        for form_940 in self:
            form_940.payslip_ids = form_940.allowed_payslip_ids

    def _get_allowed_payslips_domain(self):
        self.ensure_one()
        return [
            ('state', 'in', ['validated', 'paid']),
            ('date_from', '>=', date(int(self.year), 1, 1)),
            ('date_to', '<=', date(int(self.year), 12, 31)),
            ('company_id', '=', self.company_id.id),
        ]

    @api.depends('company_id', 'year')
    def _compute_allowed_payslip_ids(self):
        for form_940 in self:
            allowed_payslips = self.env['hr.payslip'].search(form_940._get_allowed_payslips_domain())
            form_940.allowed_payslip_ids = allowed_payslips

    def action_generate_csv(self):
        self.ensure_one()
        header = (
            "Form Type*",
            "Tax Year*",
            "Employer EIN*",
            "Business name*",
            "Business structure or classification*",
            "Trade name (if any)",
            "Is Foreign Address*",
            "US Address 1*",
            "US Address 2",
            "US City/Town*",
            "US State*",
            "US ZIP code*",
            "Foreign  Address 1*",
            "Foreign  Address 2",
            "Foreign City/Town*",
            "Foreign State/Province*",
            "ZIP code/Postal code*",
            "Foreign Country*",
            "Email address",
            "Phone number",
            "Signatory name*",
            "Signatory Title*",
            "Daytime phone*",
            "Have you made any payments to employees in the Tax Year?*",
            "1a)Select State, if you paid unemployment tax in one state only",
            "1b) Are you a multi state employer? (Complete Schedule A)*",
            "2) Paid wages in a state that is subject to CREDIT REDUCTION?*",
            "3) Total payments to all employees",
            "4) Payments exempt from FUTA tax",
            "4a) Is the payments exempt include Fringe benefits?",
            "4b) Is the payments exempt include Group-term life insurance?",
            "4c) Is the payments exempt include Retirement/Pension?",
            "4d) Is the payments exempt include Dependent care?",
            "4e) Is the payments exempt for other reason?",
            "5) Total payments made to each employee in excess of $7000",
            "9) Were ALL the taxable FUTA wages you paid excluded from SUTA?",
            "10) FUTA Tax Adjustment Amount (Calculated from Worksheet)",
            "13) FUTA tax deposited for the year",
            "15) Choose how to use your IRS Credit (Overpayment)",
            "IRS Payment Option",
            "EFW Account Type (Required only if the IRS payment type is EFW)",
            "EFW US Bank Account Number",
            "EFW US Bank Routing number",
            "EFW Taxpayer day time Phone number",
            "16a) Report the amt of your FUTA taxable liability for 1st quarter",
            "16b) Report the amt of your FUTA taxable liability for 2nd quarter",
            "16c) Report the amt of your FUTA taxable liability for 3rd quarter",
            "16d) Report the amt of your FUTA taxable liability for 4th quarter",
            "Are you a successor employer?",
            "Is your business has closed or you stopped paying wages?",
            "Recordkeeper Name",
            "Recordkeeper Address 1",
            "Recordkeeper Address 2",
            "Recordkeeper City/Town",
            "Record Keeper State",
            "RecordKeeper ZIP code/Postal code",
            "Designee name",
            "Designee phone",
            "Designee PIN",
            "94x Online Signature PIN",
            "RA PIN",
            "Taxpayer PIN (For ERO)",
        )

        company = self.company_id
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(header)

        def total(code):
            return abs(line_values[code]['sum']['total'])

        line_values = self.payslip_ids._get_line_values([
            "401KMATCHING",
            "COMMUTER",
            "COMPANYFUTA",
            "DENTAL",
            "GROSS",
            "MEDICAL",
            "MEDICALFSA",
            "MEDICALFSADC",
            "MEDICALHSA",
            "VISION",
        ], compute_sum=True)

        quarter_to_payslips = self.payslip_ids.grouped(lambda payslip: date_utils.get_quarter_number(payslip.date_from))
        quarter_to_futa = {
            quarter: payslips._get_line_values(["COMPANYFUTA"], compute_sum=True)["COMPANYFUTA"]["sum"]["total"]
            for quarter, payslips in sorted(quarter_to_payslips.items())
        }

        categ_pretax = abs(self.payslip_ids._get_category_data("PRETAX")["total"])
        categ_matching = abs(self.payslip_ids._get_category_data("MATCHING")["total"])

        bank_account = self.company_id.partner_id.bank_ids[:1]
        row = [
            "Form 940",
            self.year,
            company.vat,
            company.name,
            dict(company._fields['l10n_us_business_structure']._description_selection(self.env)).get(company.l10n_us_business_structure),
            "",
            "No",
            company.street,
            company.street2,
            company.city,
            company.state_id.code,
            company.zip,
            *[""] * 6,
            company.email,
            company.phone,
            company.l10n_us_signatory_id.name,
            company.l10n_us_signatory_id.job_title,
            company.l10n_us_signatory_id.phone,
            "Yes",
            self.single_state_payer_id.name,
            "Yes" if self.is_multi_state_employer else "No",
            "Yes" if self.has_paid_credit_reduction_state else "No",
            total("GROSS") + categ_pretax + categ_matching,
            categ_pretax + total("401KMATCHING"),
            "Yes" if any(total(code) > 0 for code in ("MEDICAL", "DENTAL", "VISION", "MEDICALFSA", "MEDICALHSA", "COMMUTER")) else "No",
            "No",
            "Yes" if total("401KMATCHING") > 0 else "No",
            "Yes" if total("MEDICALFSADC") > 0 else "No",
            "",
            max(0, total("GROSS") - categ_pretax - total("401KMATCHING") - 7_000),
            *[""] * 2,
            total("COMPANYFUTA"),
            "",
            dict(self._fields['irs_payment_option']._description_selection(self.env)).get(self.irs_payment_option),
            dict(bank_account._fields['l10n_us_bank_account_type']._description_selection(self.env)).get(bank_account.l10n_us_bank_account_type),
            bank_account.acc_number,
            bank_account.clearing_number,
            company.phone,
            quarter_to_futa.get(1),
            quarter_to_futa.get(2),
            quarter_to_futa.get(3),
            quarter_to_futa.get(4),
            "No",
            "No",
            "",
            company.street,
            company.street2,
            company.city,
            company.state_id.code,
            company.zip,
            *[""] * 6,
        ]
        writer.writerow([col or "" for col in row])  # never write False

        self.csv_file = base64.b64encode(output.getvalue().encode())
        self.csv_filename = f"form_940_{self.year}.csv"
