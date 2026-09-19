from . import controllers
from . import models


def _post_init_hook(env):
    cl_extra_step = env.ref('l10n_cl_edi_website_sale.checkout_step_invoicing')
    for website in env['website'].search([]):
        cl_extra_step.copy({'website_id': website.id})
