# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import csv
import io

from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import date_utils


class L10nUsForm941(models.Model):
    _name = 'l10n.us.941'
    _description = 'Form 941'

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "US":
            raise UserError(_('You must be logged in a US company to use this feature'))
        return super().default_get(fields)

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
    tax_liability = fields.Selection([
        ("min_liability", "Min Tax Liability"),
        ("monthly", "Monthly"),
        ("semiweekly", "Semiweekly (Schedule B)"),
    ], required=True, string="Deposit Schedule and Tax Liability", help="This determines your required tax deposit schedule based on your business's employment tax liability amount.")
    year = fields.Char(required=True, default=lambda self: fields.Date.today().year, string="Tax Year")
    quarter = fields.Selection([
        ('1', 'Q1 (Jan-Mar)'),
        ('2', 'Q2 (Apr-Jun)'),
        ('3', 'Q3 (Jul-Sep)'),
        ('4', 'Q4 (Oct-Dec)'),
    ], required=True, default=lambda self: str(date_utils.get_quarter_number(fields.Date.today())), string="Quarter")
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

    @api.depends('year', 'quarter')
    def _compute_display_name(self):
        for form_941 in self:
            form_941.display_name = f"Form 941 - {form_941.year} {form_941.quarter}"

    @api.depends('allowed_payslip_ids')
    def _compute_payslips_ids(self):
        for form_941 in self:
            form_941.payslip_ids = form_941.allowed_payslip_ids

    def _get_date_range(self):
        self.ensure_one()
        year = int(self.year)
        month = int(self.quarter) * 3
        return date_utils.get_quarter(date(year, month, 1))

    def _get_allowed_payslips_domain(self):
        self.ensure_one()
        date_from, date_to = self._get_date_range()
        return [
            ('state', 'in', ['validated', 'paid']),
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
            ('company_id', '=', self.company_id.id),
        ]

    @api.depends('company_id', 'year', 'quarter')
    def _compute_allowed_payslip_ids(self):
        for form_941 in self:
            allowed_payslips = self.env['hr.payslip'].search(form_941._get_allowed_payslips_domain())
            form_941.allowed_payslip_ids = allowed_payslips

    def _get_month_to_tax_liability(self):
        month_from = self._get_date_range()[0].month
        month_to_payslips = self.payslip_ids.grouped(lambda payslip: payslip.date_from.month)
        tax_liability_codes = ["FIT", "SST", "COMPANYSOCIAL", "MEDICARE", "COMPANYMEDICARE", "MEDICAREADD"]
        month_to_tax_liability = {}

        for month, payslips in sorted(month_to_payslips.items()):
            tax_liability_lines = payslips._get_line_values(tax_liability_codes, compute_sum=True)
            month_to_tax_liability[month - month_from] = sum(abs(tax_liability_lines[code]["sum"]["total"]) for code in tax_liability_codes)

        return month_to_tax_liability

    def action_generate_csv(self):
        self.ensure_one()
        header = (
            "Form Type*",
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
            "Foreign Address 1*",
            "Foreign Address 2",
            "Foreign City/Town*",
            "Foreign State/Province*",
            "Postal code*",
            "Foreign Country*",
            "Email address",
            "Phone number",
            "Signatory name*",
            "Signatory title*",
            "Daytime phone*",
            "Tax Year*",
            "Quarter*",
            "1) Total number of employees",
            "2) Total wages, tips, and other compensation",
            "3) Total Federal Income Tax Withheld",
            "5a) Taxable social security wages (Column1)",
            "5b) Taxable social security tips (Column1)",
            "5c) Taxable Medicare wages & tips (Column1)",
            "5d) Wages & tips subject to Add Medi Tax withhold (Column1)",
            "5f) Section 3121(q) Tax due on unreported tips",
            "7) adjustment for fractions of cents from Employees share",
            "8) adjustment for sick pay",
            "9) adjustments for tips and group-term life insurance",
            "11) Qualified Small Business payroll tax credit",
            "13) Total deposits for this quarter",
            "choose how to use your IRS Credit, If return has Overpayment",
            "IRS Payment Option",
            "(EFW)Account Type*",
            "(EFW)US Bank Account Number*",
            "(EFW)US Bank Routing Number*",
            "(EFW)Taxpayer day time Phone Number*",
            "Deposit Schedule & Tax Liability*",
            "Tax liability Month 1",
            "Tax liability Month 2",
            "Tax liability Month 3",
            "Is your business has closed or you stopped paying wages",
            "Enter the final date you paid wages",
            "Recordkeeper name",
            "Recordkeeper Address 1*",
            "Recordkeeper Address 2",
            "Recordkeeper City/Town*",
            "Recordkeeper State/Province*",
            "Recordkeeper ZIP code/Postal code*",
            "Is seasonal employer",
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
            "401K",
            "COMPANYMEDICARE",
            "COMPANYSOCIAL",
            "FIT",
            "MEDICARE",
            "MEDICAREADD",
            "SST",
            "TAXABLE",
            "TIPS",
        ], compute_sum=True)
        month_to_tax_liability = self._get_month_to_tax_liability()

        bank_account = self.company_id.partner_id.bank_ids[:1]
        row = [
            "Form 941",
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
            self.year,
            dict(self._fields['quarter']._description_selection(self.env)).get(self.quarter),
            len(self.payslip_ids.mapped("employee_id")),
            total("TAXABLE"),
            total("FIT"),
            total("TAXABLE") + total("401K") - total("TIPS"),
            total("TIPS"),
            total("TAXABLE") + total("401K"),
            total("TAXABLE") + total("401K") if total("MEDICAREADD") > 0 else 0,
            *[""] * 5,
            total("FIT") + total("SST") + total("COMPANYSOCIAL") + total("MEDICARE") + total("COMPANYMEDICARE") + total("MEDICAREADD"),
            "",
            dict(self._fields['irs_payment_option']._description_selection(self.env)).get(self.irs_payment_option),
            dict(bank_account._fields['l10n_us_bank_account_type']._description_selection(self.env)).get(bank_account.l10n_us_bank_account_type),
            bank_account.acc_number,
            bank_account.clearing_number,
            company.phone,
            dict(self._fields['tax_liability']._description_selection(self.env)).get(self.tax_liability),
            month_to_tax_liability.get(0),
            month_to_tax_liability.get(1),
            month_to_tax_liability.get(2),
            "No",
            *[""] * 2,
            company.street,
            company.street2,
            company.city,
            company.state_id.code,
            company.zip,
            "No",
            *[""] * 6,
        ]
        writer.writerow([col or "" for col in row])  # never write Falsy, should be ok to make 0 blank

        self.csv_file = base64.b64encode(output.getvalue().encode())
        self.csv_filename = f"form_941_{self.year}_{self.quarter}.csv"
