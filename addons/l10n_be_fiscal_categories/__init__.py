# Part of Odoo. See LICENSE file for full copyright and licensing details.
from . import models


def _l10n_be_fiscal_categories_post_init(env):
    for company in env['res.company'].search([('chart_template', 'in', ('be_comp', 'be_asso')), ('parent_id', '=', False)]):
        Template = env['account.chart.template'].with_company(company)
        fiscal_accounts = {
            xmlid: vals
            for xmlid, vals in Template._get_be_fiscal_accounts().items()
            if Template.ref(xmlid, raise_if_not_found=False)
        }
        if fiscal_accounts:
            Template._load_data({
                'account.account': fiscal_accounts,
            })
