# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    _transaction_code_domain = '''
        [('type', '=', 'transaction'),
        '|', ('expiry_date', '>', context_today().strftime('%Y-%m-%d')), ('expiry_date', '=', None),
        '|', ('start_date', '<', context_today().strftime('%Y-%m-%d')), ('start_date', '=', None)]
    '''

    company_country_id = fields.Many2one(
        'res.country', string="Company country", readonly=True,
        related='company_id.account_fiscal_country_id'
    )
    intrastat_default_invoice_transaction_code_id = fields.Many2one(
        'account.intrastat.code',
        string='Default invoice transaction code',
        related='company_id.intrastat_default_invoice_transaction_code_id',
        domain=_transaction_code_domain,
        readonly=False,
    )
    intrastat_default_refund_transaction_code_id = fields.Many2one(
        'account.intrastat.code',
        string='Default refund transaction code',
        related='company_id.intrastat_default_refund_transaction_code_id',
        domain=_transaction_code_domain,
        readonly=False,
    )
    intrastat_region_id = fields.Many2one(
        comodel_name='account.intrastat.code',
        string='Intrastat region',
        related='company_id.intrastat_region_id',
        domain="[('type', '=', 'region'), '|', ('country_id', '=', False), ('country_id', '=', company_country_id)]",
        readonly=False,
    )
    has_country_regions = fields.Boolean(compute="_compute_has_country_regions")

    @api.depends('intrastat_region_id')
    def _compute_has_country_regions(self):
        regions_without_country = self.env['account.intrastat.code'].search_count(
            domain=[('type', '=', 'region'), ('country_id', '=', False)],
            limit=1,
        )
        if regions_without_country:
            self.has_country_regions = True
        else:
            regions_counts_groupby_country = dict(self.env['account.intrastat.code']._read_group(
                domain=[('type', '=', 'region'), ('country_id', 'in', self.company_country_id.ids)],
                groupby=['country_id'], aggregates=['__count'],
            ))
            for record in self:
                record.has_country_regions = regions_counts_groupby_country.get(record.company_country_id)
