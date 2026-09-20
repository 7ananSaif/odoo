# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from .hr_version import CANTONS


class HrPayslipIsLogLine(models.Model):
    _name = 'hr.payslip.is.log.line'
    _description = 'IS Log lines'

    is_code = fields.Char()
    amount = fields.Float()
    is_correction = fields.Boolean()
    date = fields.Date()

    payslip_id = fields.Many2one('hr.payslip', ondelete="cascade")
    source_tax_canton = fields.Selection(selection=CANTONS)
    source_tax_municipality = fields.Char()
    correction_type = fields.Selection(selection=[("old", "Old"),
                                                  ("new", "New")])
    is_correction_id = fields.Many2one("hr.employee.is.line", string="Related Correction")
    allowed_correction_payslips_ids = fields.Many2many(related='is_correction_id.payslips_to_correct')
    code = fields.Selection(selection=[("ISDTSALARYPERIODIC", "Periodic ST Determinant Salary"),
                                       ("ASDAYS", "Insurance Days"),
                                       ("ISWORKEDDAYS", "Source-tax Worked Days"),
                                       ("ISWORKEDDAYSINCH", "Source-tax Worked Days in Switzerland"),
                                       ("ISDTSALARYAPERIODIC", "Aperiodic ST Determinant Salary"),
                                       ("ISSALARY", "ST Salary"),
                                       ("ISDTSALARY", "ST Rate Determinant Salary"),
                                       ("IS", "Source Tax Amount")], required=True)

    tax_at_source_category = fields.Selection(string="Tax Scale Type", selection=[('TaxAtSourceCode', 'Tariff Code'),
                                                                                  ('CategoryPredefined', "Predefined Category"),
                                                                                  ('CategoryOpen', "Open")])
    corrected_slip_id = fields.Many2one('hr.payslip', domain="[('id', 'in', allowed_correction_payslips_ids)]")
