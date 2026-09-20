# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import tagged
from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon, EXTERNAL_MODE


@tagged('post_install_l10n', 'post_install', '-at_install', *(['-standard', 'external'] if EXTERNAL_MODE else []))
class TestMxEdiHrPayrollCommon(TestMxEdiCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids += cls.env.ref('hr_payroll.group_hr_payroll_user')
        cls.company.partner_id.zip = '20000'
        cls.company.l10n_mx_imss_id = 'B5510768108'
        cls.company.vat = 'URE180429TM6'

        cls.partner_employee = cls.env['res.partner'].create({
            'name': "Ingrid Xodar Jimenez",
            'country_id': cls.env.ref('base.mx').id,
            'state_id': cls.env.ref('base.state_mx_jal').id,
        })

        cls.bank_account = cls.env['res.partner.bank'].create({
            'acc_number': '1111111111',
            'bank_id': cls.env.ref('l10n_mx.acc_bank_002_BANAMEX').id,
            'partner_id': cls.partner_employee.id,
        })

        cls.department = cls.env['hr.department'].create({
            'name': 'Desarrollo',
            'company_id': cls.company.id,
        })

        cls.job = cls.env['hr.job'].sudo().create({
            'name': 'Ingeniero de Software',
            'company_id': cls.company.id,
        })

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Ingrid Xodar Jimenez',
            'company_id': cls.company.id,
            'bank_account_ids': cls.bank_account.ids,
            'l10n_mx_rfc': 'XOJI740919U48',
            'registration_number': '120',
            'ssnid': '000000',
            'l10n_mx_curp': 'XEXX010101HNEXXXA4',
            'private_zip': '76028',
            'work_contact_id': cls.partner_employee.id,
            'department_id': cls.department.id,
            'job_id': cls.job.id,
            'date_version': '2015-01-01',
            'contract_date_start': '2015-01-01',
            'l10n_mx_regime_type': '03',
            'contract_type_id': cls.env.ref('l10n_mx_hr_payroll_account_edi.l10n_mx_contract_type_01').id,
            'wage': 5000,
            'schedule_pay': 'bi-weekly',
        })

    def _assert_payslip_cfdi(self, payslip, filename):
        document = payslip.l10n_mx_edi_document_ids.filtered(lambda x: x.state == 'payslip_sent')[:1]
        self.assertTrue(document)
        self._assert_document_cfdi(document, filename)

    def _generate_payslip_with_cfdi(self, lines_values=None, other_inputs=None):
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'name': 'Payslip',
            'date_from': '2024-05-09',
            'date_to': '2024-05-24',
            'struct_id': self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay').id,
        })
        # We can add other inputs to trigger some rules needed for some testing files
        if other_inputs:
            input_values = []
            for xmlid, value in other_inputs.items():
                input_values.append({
                    'payslip_id': payslip.id,
                    'input_type_id': self.env.ref(xmlid).id,
                    'amount': value,
                })
            self.env['hr.payslip.input'].create(input_values)
        payslip.compute_sheet()

        # We can edit the payslip lines to have the same amounts and concepts as in the test_files
        if lines_values:
            action = payslip.action_edit_payslip_lines()
            wizard = self.env[action['res_model']].browse(action['res_id'])
            line_ids_by_code = wizard.line_ids.grouped('code')
            for code, value in lines_values.items():
                if code in line_ids_by_code:
                    line_ids_by_code[code].amount = value
            wizard.action_validate_edition()

        payslip.action_payslip_done()
        payslip.move_id.action_post()
        payslip.action_payslip_paid()
        with self.mx_external_setup(self.frozen_today), self.with_mocked_pac_sign_success():
            payslip._l10n_mx_edi_cfdi_try_send()
        return payslip

    def test_cfdi_nomina(self):
        payslip = self._generate_payslip_with_cfdi(
            lines_values={
                'ISR': 100,
                'IMSS_EMPLOYEE_TOTAL': 200,
                'CEAV_IMSS_EMPLOYEE': 0,
                'SUBSIDY': 0,
            })
        self._assert_payslip_cfdi(payslip, 'test_cfdi_nomina')

    def test_cfdi_nomina_con_bonos_fondo_ahorro_y_deducciones(self):
        self.employee.wage = 3000
        self.employee.l10n_mx_savings_fund = 500
        payslip = self._generate_payslip_with_cfdi(
            lines_values={
                'ISR': 100,
                'IMSS_EMPLOYEE_TOTAL': 200,
                'CEAV_IMSS_EMPLOYEE': 0,
                'SUBSIDY': 0,
            },
            other_inputs={
                'l10n_mx_hr_payroll.l10n_mx_input_bonus': 150
            })
        self._assert_payslip_cfdi(payslip, 'test_cfdi_nomina_con_bonos_fondo_ahorro_y_deducciones')
