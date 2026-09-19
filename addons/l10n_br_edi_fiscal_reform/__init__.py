from . import models

from odoo.tools.sql import create_column, table_exists


def _pre_init_hook(env):
    # This module is introduced in stable, avoid the ORM on potentially large tables.
    # l10n_br_entity_type, set the right value immediately so they're ready for use
    create_column(env.cr, "res_partner", "l10n_br_entity_type", "varchar")
    query = '''
        UPDATE res_partner
           SET l10n_br_entity_type = CASE WHEN is_company THEN 'business'
                                          ELSE 'individual'
                                      END
    '''
    env.cr.execute(query)

    # l10n_br_presence, it's ok for these to remain empty
    create_column(env.cr, "account_move", "l10n_br_presence", "varchar")
    if table_exists(env.cr, "sale_order"):
        create_column(env.cr, "sale_order", "l10n_br_presence", "varchar")

    # l10n_br_is_cbs_ibs_taxpayer, True by default
    create_column(env.cr, "res_partner", "l10n_br_is_cbs_ibs_taxpayer", "bool")
    env.cr.execute("UPDATE res_partner SET l10n_br_is_cbs_ibs_taxpayer = TRUE")

    # l10n_br_is_cbs_ibs_taxpayer, True by default
    create_column(env.cr, "res_partner", "l10n_br_is_cbs_ibs_normal", "bool")
    env.cr.execute("UPDATE res_partner SET l10n_br_is_cbs_ibs_normal = TRUE")


def _l10n_br_res_company_post_init(env):
    for company in env['res.company'].search([('chart_template', '=', 'br')]):
        ChartTemplate = env['account.chart.template'].with_company(company)
        ChartTemplate._load_data({
            'res.company': ChartTemplate._get_br_res_company_l10n_br_is_icbs(company.chart_template),
        })
