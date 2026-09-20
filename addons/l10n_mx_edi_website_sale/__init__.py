# coding: utf-8

from . import models
from . import controllers


def _post_init_hook(env):
    mx_extra_step = env.ref('l10n_mx_edi_website_sale.checkout_step_invoicing')
    for website in env['website'].search([]):
        mx_extra_step.copy({'website_id': website.id})
