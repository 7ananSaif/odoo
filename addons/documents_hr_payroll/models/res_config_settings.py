# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    documents_hr_payslips_tags = fields.Many2many('documents.tag', 'payslip_tags_table',
                                    related='company_id.documents_hr_payslips_tags', readonly=False,
                                    string="Payslip")
