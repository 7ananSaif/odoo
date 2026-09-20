# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrPayslipInputType(models.Model):
    _inherit = "hr.payslip.input.type"
    _order = "l10n_au_payment_type"
    currency_id = fields.Many2one(
        "res.currency", string="Currency",
        default=lambda self: self.env.company.currency_id,
    )
    l10n_au_default_amount = fields.Monetary(
        string="Default Amount", currency_field="currency_id",
        help="Default amount for this input type")
    l10n_au_etp_type = fields.Selection(
        selection=[
            ('excluded', 'Excluded'),
            ('non_excluded', 'Non-Excluded')],
        string="ETP Type")

    l10n_au_payment_type = fields.Selection(
        selection=[
            ("etp", "ETP"),
            ("allowance", "Allowance"),
            ("deduction", "Deduction"),
            ("leave", "Leave"),
            ("other", "Other"),
        ],
        string="Payment Type",
    )

    l10n_au_superannuation_treatment = fields.Selection(
        selection=[
            ("ote", "OTE"),
            ("salary", "Salary & Wages"),
            ("not_salary", "Not Salary & Wages"),
        ],
        string="Superannuation Treatment",
    )

    l10n_au_paygw_treatment = fields.Selection(
        [('regular', 'Regular'),
        ('no_paygw', 'No PAYG Withholding'),
        ('special', 'Taxed above ATO limit'),
        ],
        string="PAYGW Treatment",
    )

    l10n_au_payroll_code = fields.Selection(
        selection=[
            ("LD", "LD"),
            ("MD", "MD"),
            ("AD", "AD"),
            ("OD", "OD"),
            ("RD", "RD"),
            ("G", "G"),
            ("T", "T"),
            ("X", "X"),
            ("Bonus and Commissions", "Bonus and Commissions"),
            ("E", "E"),
            ("R", "R"),
            ("Overtime", "Overtime"),
            ("W", "W"),
            ("QN", "QN"),
            ("Directors' fees", "Directors' fees"),
            ("KN", "KN"),
            ("C", "C"),
            ("CD", "CD"),
            ("O", "O"),
            ("F", "F"),
            ("Gross", "Gross"),
        ],
        string="STP Code",
    )
    l10n_au_payroll_code_description = fields.Selection(
        selection=[
            ('G1', 'G1'),
            ('H1', 'H1'),
            ('ND', 'ND'),
            ('T1', 'T1'),
            ('U1', 'U1'),
            ('V1', 'V1'),
        ],
        string="Payroll Code Description",
    )
    l10n_au_quantity = fields.Boolean(string="Quantity")
    l10n_au_requires_details = fields.Boolean(string="Requires Details")
    l10n_au_input_uom = fields.Selection([("days", "Day(s)"), ("kms", "Kilometer(s)")], string="Input UoM")
