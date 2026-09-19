# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def action_redirect_website_generator(self):
        # Name not relevant as it will be overwritten by the website_generator
        website = self.env['website'].create({
            'name': _('Imported Website'),
        })
        website._force()
        website_generator_not_installed = self.env['ir.module.module'].search(
            [('name', '=', 'website_generator'), ('state', '=', 'uninstalled')]
        )
        if website_generator_not_installed:
            website_generator_not_installed.button_immediate_install()
        return {
            'type': 'ir.actions.act_url',
            'url': '/website/configurator/6',  # See WEBSITE_GENERATOR_ROUTE
            'target': 'self',
        }
