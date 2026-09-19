from odoo import models


class IrCronTrigger(models.Model):
    _inherit = 'ir.cron.trigger'

    def _check_image_cron_is_not_already_triggered(self):
        pass  # To remove in master
