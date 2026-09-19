# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

from odoo.addons.crm_enterprise.tools.business_card_scanner import BusinessCardScanner


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    days_to_convert = fields.Float('Days To Convert', compute='_compute_days_to_convert', store=True)
    days_exceeding_closing = fields.Float('Exceeded Closing Days', compute='_compute_days_exceeding_closing', store=True)

    @api.depends('date_conversion', 'create_date')
    def _compute_days_to_convert(self):
        for lead in self:
            if lead.date_conversion:
                lead.days_to_convert = (fields.Datetime.from_string(lead.date_conversion) - fields.Datetime.from_string(lead.create_date)).days
            else:
                lead.days_to_convert = 0

    @api.depends('date_deadline', 'date_closed')
    def _compute_days_exceeding_closing(self):
        for lead in self:
            if lead.date_closed and lead.date_deadline:
                lead.days_exceeding_closing = (fields.Datetime.from_string(lead.date_deadline) - fields.Datetime.from_string(lead.date_closed)).days
            else:
                lead.days_exceeding_closing = 0

    def action_ocr_business_cards(self, attachment_ids):
        attachments = self.env['ir.attachment'].browse(attachment_ids)
        card_scanner = BusinessCardScanner(self.env)
        leads = card_scanner.business_cards_to_leads(attachments)

        if not leads:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'info',
                    'sticky': False,
                    'message': _("The AI agent was not able to generate a lead from the provided image. *sad robot noises* 🤖"),
                }
            }

        action = self.env["ir.actions.actions"]._for_xml_id("crm.crm_lead_opportunities")
        if len(leads) == 1:
            action.update({
                'views': [[False, "form"]],
                'view_mode': 'form',
                'res_id': leads[0].id,
            })
        else:
            action.update({
                'domain': [('id', 'in', leads.ids)],
                'views': [[False, "list"], [False, "kanban"], [False, "form"]],
                'view_mode': 'list,kanban,form',
            })

        return action
