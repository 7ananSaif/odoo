# Part of Odoo. See LICENSE file for full copyright and licensing details.

import uuid

from odoo import models, fields, api, _
from odoo.fields import Date
from odoo.exceptions import UserError


class L10n_UkHmrcSendWizard(models.TransientModel):
    _name = 'l10n_uk.hmrc.send.wizard'
    _description = "HMRC Send Wizard"

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if 'client_data' not in self.env.context:
            return res

        # Check obligations: should be logged in by now
        self.env['l10n_uk.vat.obligation'].import_vat_obligations(self.env.context['client_data'])

        if 'obligation_id' in fields:
            obligations = self.env['l10n_uk.vat.obligation'].search([('status', '=', 'open')])
            if not obligations:
                raise UserError(_('You have no open obligations anymore'))

            date_from = Date.to_date(self.env.context['options']['date']['date_from'])
            date_to = Date.to_date(self.env.context['options']['date']['date_to'])
            for obl in obligations:
                if obl.date_start == date_from and obl.date_end == date_to:
                    res['obligation_id'] = obl.id
                    break

        if 'hmrc_gov_client_device_id' in fields:
            res['hmrc_gov_client_device_id'] = self.env.context['client_data']['hmrc_gov_client_device_id']

        if 'message' in fields:
            res['message'] = not res.get('obligation_id')
        return res

    obligation_id = fields.Many2one('l10n_uk.vat.obligation', 'Obligation', domain=[('status', '=', 'open')], required=True)
    message = fields.Boolean('Message', readonly=True) # Show message if no obligation corresponds to report options
    accept_legal = fields.Boolean('Accept Legal Statement') # A checkbox to warn the user that what he sends is legally binding
    hmrc_gov_client_device_id = fields.Char(default=lambda x: uuid.uuid4())
