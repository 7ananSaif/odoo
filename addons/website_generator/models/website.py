# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools.urls import urljoin as url_join

from odoo.addons.iap.tools.iap_tools import iap_jsonrpc
from odoo.addons.website_generator.models.generator import DEFAULT_WSS_ENDPOINT


class Website(models.Model):
    _inherit = 'website'

    @api.model
    def import_website(self, **kwargs):
        vals = {
            'target_url': self._normalize_domain_url(kwargs['url']),
        }

        modules_to_install = self.env['ir.module.module']

        # website_generator_sale
        if kwargs.get('import_products'):
            module = self.env['ir.module.module'].search([('name', '=', 'website_generator_sale')])
            if module.state != 'installed':
                modules_to_install += module
            vals['import_products'] = True

        # install modules
        if modules_to_install:
            modules_to_install.button_immediate_install()

        request = self.env['website_generator.request'].create(vals)

        if request.status != 'waiting':
            raise UserError(request.status_message)

        self.configurator_skip()

        return True

    @api.model
    def url_check(self, url_to_check):
        self.env['website_generator.request'].check_access('create')
        target_url = self._normalize_domain_url(url_to_check)

        ICP = self.env['ir.config_parameter'].sudo()
        ws_endpoint = ICP.get_param('website_scraper_endpoint', DEFAULT_WSS_ENDPOINT)
        url = url_join(ws_endpoint, '/website_scraper/check_url_reachable')
        params = {
            'url': target_url,
        }

        return iap_jsonrpc(url, params=params)
