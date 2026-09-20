# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrAppraisalNote(models.Model):
    _name = 'hr.appraisal.note'
    _description = "Appraisal Assessment Note"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one('res.company', index=True, domain=lambda self: [('id', 'in', self.env.companies.ids)])
