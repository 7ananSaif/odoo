# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64

from odoo.addons.l10n_us_hr_payroll.tests.common import CommonTestPayslips
from odoo.tests import tagged, freeze_time


@tagged('post_install_l10n', 'post_install', '-at_install')
@freeze_time("2025-08-14 10:00:00")
class TestTaxForms(CommonTestPayslips):
    """Only provides very basic test coverage that doesn't include payslip data. We could consider moving these tests
    to test_l10n_us_hr_payroll at some point for more comprehensive coverage."""
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.us_company = cls.env['res.company'].create({
            'name': 'US Company (Tax Form test)',
            'country_id': cls.env.ref('base.us').id,
            'l10n_us_business_structure': 'c_corp',
        })
        cls.env.user.company_ids |= cls.us_company
        cls.env.user.company_id = cls.us_company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.us_company.ids))

        cls.env['res.partner.bank'].create({
            'partner_id': cls.us_company.partner_id.id,
            'acc_number': '0123456789',
            'l10n_us_bank_account_type': 'checking',
        })
        cls.us_company.l10n_us_signatory_id = cls.env['hr.employee'].create({
            'name': 'Signatory',
            'job_title': 'Title',
            'phone': '1234567890',
        })

        # don't call action_payslip_done() because when l10n_us_hr_payroll_account is installed, it will require accounting fields to be set
        cls.create_payslip_run().slip_ids.write({'state': 'validated'})

    def test_form_940(self):
        form_940 = self.env['l10n.us.940'].create({
            'single_state_payer_id': self.env.ref('base.state_us_5').id,
            'irs_payment_option': 'eftps',
            'has_paid_credit_reduction_state': True,
        })
        form_940.action_generate_csv()
        content = base64.b64decode(form_940.csv_file).decode()

        expected = '''Form Type*,Tax Year*,Employer EIN*,Business name*,Business structure or classification*,Trade name (if any),Is Foreign Address*,US Address 1*,US Address 2,US City/Town*,US State*,US ZIP code*,Foreign  Address 1*,Foreign  Address 2,Foreign City/Town*,Foreign State/Province*,ZIP code/Postal code*,Foreign Country*,Email address,Phone number,Signatory name*,Signatory Title*,Daytime phone*,Have you made any payments to employees in the Tax Year?*,"1a)Select State, if you paid unemployment tax in one state only",1b) Are you a multi state employer? (Complete Schedule A)*,2) Paid wages in a state that is subject to CREDIT REDUCTION?*,3) Total payments to all employees,4) Payments exempt from FUTA tax,4a) Is the payments exempt include Fringe benefits?,4b) Is the payments exempt include Group-term life insurance?,4c) Is the payments exempt include Retirement/Pension?,4d) Is the payments exempt include Dependent care?,4e) Is the payments exempt for other reason?,5) Total payments made to each employee in excess of $7000,9) Were ALL the taxable FUTA wages you paid excluded from SUTA?,10) FUTA Tax Adjustment Amount (Calculated from Worksheet),13) FUTA tax deposited for the year,15) Choose how to use your IRS Credit (Overpayment),IRS Payment Option,EFW Account Type (Required only if the IRS payment type is EFW),EFW US Bank Account Number,EFW US Bank Routing number,EFW Taxpayer day time Phone number,16a) Report the amt of your FUTA taxable liability for 1st quarter,16b) Report the amt of your FUTA taxable liability for 2nd quarter,16c) Report the amt of your FUTA taxable liability for 3rd quarter,16d) Report the amt of your FUTA taxable liability for 4th quarter,Are you a successor employer?,Is your business has closed or you stopped paying wages?,Recordkeeper Name,Recordkeeper Address 1,Recordkeeper Address 2,Recordkeeper City/Town,Record Keeper State,RecordKeeper ZIP code/Postal code,Designee name,Designee phone,Designee PIN,94x Online Signature PIN,RA PIN,Taxpayer PIN (For ERO)
Form 940,2025,,US Company (Tax Form test),C Corporation or LLC as C Corp,,No,,,,,,,,,,,,,,Signatory,Title,,Yes,California,No,Yes,6000.0,,No,No,No,No,,,,,,,EFTPS,Checking,0123456789,,,,,,,No,No,,,,,,,,,,,,'''

        for expected, generated in zip(expected.splitlines(), content.splitlines()):
            self.assertEqual(expected, generated)

    def test_form_941(self):
        form_941 = self.env['l10n.us.941'].create({
            'irs_payment_option': 'eftps',
            'tax_liability': 'monthly',
        })
        form_941.action_generate_csv()
        content = base64.b64decode(form_941.csv_file).decode()

        expected = '''Form Type*,Employer EIN*,Business name*,Business structure or classification*,Trade name (if any),Is Foreign Address*,US Address 1*,US Address 2,US City/Town*,US State*,US ZIP code*,Foreign Address 1*,Foreign Address 2,Foreign City/Town*,Foreign State/Province*,Postal code*,Foreign Country*,Email address,Phone number,Signatory name*,Signatory title*,Daytime phone*,Tax Year*,Quarter*,1) Total number of employees,"2) Total wages, tips, and other compensation",3) Total Federal Income Tax Withheld,5a) Taxable social security wages (Column1),5b) Taxable social security tips (Column1),5c) Taxable Medicare wages & tips (Column1),5d) Wages & tips subject to Add Medi Tax withhold (Column1),5f) Section 3121(q) Tax due on unreported tips,7) adjustment for fractions of cents from Employees share,8) adjustment for sick pay,9) adjustments for tips and group-term life insurance,11) Qualified Small Business payroll tax credit,13) Total deposits for this quarter,"choose how to use your IRS Credit, If return has Overpayment",IRS Payment Option,(EFW)Account Type*,(EFW)US Bank Account Number*,(EFW)US Bank Routing Number*,(EFW)Taxpayer day time Phone Number*,Deposit Schedule & Tax Liability*,Tax liability Month 1,Tax liability Month 2,Tax liability Month 3,Is your business has closed or you stopped paying wages,Enter the final date you paid wages,Recordkeeper name,Recordkeeper Address 1*,Recordkeeper Address 2,Recordkeeper City/Town*,Recordkeeper State/Province*,Recordkeeper ZIP code/Postal code*,Is seasonal employer,Designee name,Designee phone,Designee PIN,94x Online Signature PIN,RA PIN,Taxpayer PIN (For ERO)
Form 941,,US Company (Tax Form test),C Corporation or LLC as C Corp,,No,,,,,,,,,,,,,,Signatory,Title,,2025,Q3 (Jul-Sep),2,,,,,,,,,,,,,,EFTPS,Checking,0123456789,,,Monthly,,,,No,,,,,,,,No,,,,,,'''

        for expected, generated in zip(expected.splitlines(), content.splitlines()):
            self.assertEqual(expected, generated)
