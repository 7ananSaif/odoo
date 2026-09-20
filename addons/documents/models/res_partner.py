# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ResPartner(models.Model):
    _inherit = "res.partner"

    document_ids = fields.One2many('documents.document', 'partner_id', string='Documents')
    document_count = fields.Integer('Document Count', compute='_compute_document_count')

    def _compute_document_count(self):
        document_count_dict = dict(self.env['documents.document']._read_group(
            [('partner_id', 'in', self.ids)],
            groupby=['partner_id'],
            aggregates=['__count']))

        for record in self:
            record.document_count = document_count_dict.get(record, 0)

    def action_see_documents(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('documents.document_action_preference')
        return action | {
            'domain': [('partner_id', '=', self.id)],
            'context': {
                'default_partner_id': self.id,
                'searchpanel_default_user_folder_id': False,
            },
        }

    def action_create_members_to_invite(self):
        return {
            'res_model': 'res.partner',
            'target': 'new',
            'type': 'ir.actions.act_window',
            'view_id': self.env.ref('base.view_partner_simple_form').id,
            'view_mode': 'form',
        }
