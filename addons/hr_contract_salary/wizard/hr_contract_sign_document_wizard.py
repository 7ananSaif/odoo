# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrContractSignDocumentWizard(models.TransientModel):
    _inherit = 'hr.contract.sign.document.wizard'

    sign_template_ids = fields.Many2many(compute='_compute_sign_template_ids', store=True, readonly=False)

    @api.depends('version_id')
    def _compute_sign_template_ids(self):
        for wizard in self:
            version = wizard.version_id
            if not version:
                continue
            current_version = version.employee_id.current_version_id
            if (version == current_version or version.date_version < current_version.date_version) and version.contract_update_template_id:
                wizard.sign_template_ids |= version.contract_update_template_id
            elif version.date_version > current_version.date_version and version.sign_template_id:
                wizard.sign_template_ids |= version.sign_template_id
