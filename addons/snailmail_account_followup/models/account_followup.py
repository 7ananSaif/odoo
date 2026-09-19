# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class Account_FollowupFollowupLine(models.Model):
    _inherit = 'account_followup.followup.line'

    send_letter = fields.Boolean('Letter', default=False)
