# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.fields import Domain


class AccountFiscalCategory(models.Model):
    _name = 'account.fiscal.category'
    _description = "Account Fiscal Category"

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    active = fields.Boolean(default=True, help="Set active to false to hide the category without removing it.")
    company_id = fields.Many2one('res.company')
    account_ids = fields.One2many('account.account', 'fiscal_category_id', check_company=True)

    _unique_code = models.Constraint(
        'UNIQUE(code)',
        "Fiscal category code should be unique.",
    )

    @api.depends('code')
    def _compute_display_name(self):
        for category in self:
            category.display_name = f"{category.code} - {category.name}" if category.code else category.name

    @api.model
    def _search_display_name(self, operator, value):
        if operator in Domain.NEGATIVE_OPERATORS:
            return NotImplemented
        if operator == 'in':
            return Domain.OR(self._search_display_name('=', v) for v in value)
        if value and isinstance(value, str):
            code_value = value.split(' ')[0]
            return Domain('code', '=ilike', f'{code_value}%') | Domain('name', operator, value)
        if operator == '=':
            operator = 'in'
            value = [value]
        return super()._search_display_name(operator, value)
