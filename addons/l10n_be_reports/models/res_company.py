# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_be_isoc_corporate_tax_rate = fields.Selection(
        selection=[
            ('25', "25 %"),
            ('20', "20 %"),
        ],
        string="Corporate Tax Rate",
        default='25',
    )

    l10n_be_region_id = fields.Many2one(
        comodel_name='l10n_be.company.region',
        compute='_compute_l10n_be_region_id',
        store=True, readonly=False,
        string="Company Region",
        groups="account.group_account_user",
        help="The region where the company is located. This is used for annual report export."
    )
    l10n_be_company_type_id = fields.Many2one(
        comodel_name='l10n_be.company.type',
        string="Company Type",
        groups="account.group_account_user",
        help="The type of company. This is used for annual report export."
    )

    def _get_countries_allowing_tax_representative(self):
        rslt = super()._get_countries_allowing_tax_representative()
        rslt.add(self.env.ref('base.be').code)
        return rslt

    @api.depends('zip')
    def _compute_l10n_be_region_id(self):
        """Compute the region based on the company's zip code."""
        for company in self:
            if (company.country_code == 'BE'
                and company.zip
                and company.zip.isdigit()
                and not company.l10n_be_region_id
            ):
                company.l10n_be_region_id = self.env['l10n_be.company.region'].search([
                    ('zip_start', '<=', company.zip),
                    ('zip_end', '>=', company.zip)
                ], limit=1)
