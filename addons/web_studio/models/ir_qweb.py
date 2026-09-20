# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class IrQweb(models.AbstractModel):
    _inherit = 'ir.qweb'

    # REPORT STUFF
    def _render(self, template, values=None, **options):
        if self.env.context.get("studio"):
            # Force inherit branding from report rendering
            return super(IrQweb, self.with_context(inherit_branding=True))._render(template, values, **options)
        return super()._render(template, values, **options)

    def _get_template_cache_keys(self):
        return super()._get_template_cache_keys() + ["studio"]

    def _prepare_environment(self, values):
        # blacklist known parasite variables
        if self.env.context.get("studio"):
            for k in ["main_object"]:
                if k in values:
                    del values[k]
        return super()._prepare_environment(values)
