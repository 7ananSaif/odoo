import logging
from json import JSONDecodeError

from odoo import _
from odoo.exceptions import UserError

from . import models
from . import controllers
from . import wizard
from .utils import make_request_stripe_proxy


_logger = logging.getLogger(__name__)


def _post_init_hook_setup_issuing(env):
    companies = env['res.company'].search([], order='parent_path')
    companies._create_stripe_issuing_journal()
    companies._stripe_issuing_setup_mcc()


def _uninstall_hook(env):
    """ Uninstall hook to delete the Stripe account, as a safeguard against accidental deletion
    we request the user to block all cards first.
    """
    if env['hr.expense.stripe.card'].search_count([('state', 'in', ['inactive', 'active'])]):
        raise UserError(_(
            "You cannot uninstall the 'Expense cards' module while there are active or inactive Stripe cards. "
            "Please manually block all cards before uninstalling the module."
        ))
    for company in env['res.company'].search([('stripe_id', '!=', False)], order='parent_path').filtered('stripe_id'):
        company_sudo = company.sudo()
        try:
            make_request_stripe_proxy(
                company_sudo,
                'accounts/{account}',
                route_params={'account': company_sudo.stripe_id},
                method='DELETE',
            )
        except JSONDecodeError as error:
            _logger.error(error)
