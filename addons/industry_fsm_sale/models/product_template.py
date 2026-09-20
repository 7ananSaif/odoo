# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    project_id = fields.Many2one(domain="['|', ('company_id', '=', False), '&', ('company_id', '=?', company_id), ('company_id', '=', current_company_id), ('allow_billable', '=', True), '|', ('pricing_type', '=', 'task_rate'), ('is_fsm', '=', True), ('allow_timesheets', 'in', [service_policy == 'delivered_timesheet', True]), ('is_template', '=', False)]")

    @api.constrains('service_type', 'type', 'invoice_policy')
    def _ensure_service_linked_to_project(self):
        service_templates = self.filtered(lambda template:
                template.service_type != 'timesheet'
                or template.type != 'service'
                or template.invoice_policy != 'delivery')
        read_group_args = {
            'domain': [('timesheet_product_id', 'in', service_templates.product_variant_ids.ids)],
            'groupby': ['timesheet_product_id'],
        }
        product_groups = self.env['project.project']._read_group(**read_group_args)
        product_groups += self.env['project.sale.line.employee.map']._read_group(**read_group_args)
        if product_groups:
            separator = "\n -   "
            templates = self.browse().union(*(product.product_tmpl_id for [product] in product_groups))
            names = separator + separator.join(templates.mapped('name'))
            raise ValidationError(_("The following products are currently associated with a Field Service project, you cannot change their Invoicing Policy or Type:%s", names))
