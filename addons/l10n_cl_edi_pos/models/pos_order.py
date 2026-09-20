# -*- coding: utf-8 -*-
from odoo import models, fields, api


class PosOrder(models.Model):
    _inherit = 'pos.order'

    invoice_type = fields.Char(string="Invoice Type")
    voucher_number = fields.Char(string="Voucher Number")

    def _prepare_invoice_vals(self):
        vals = super()._prepare_invoice_vals()
        invoice_types = self.mapped("invoice_type")
        if len(set(invoice_types)) > 1:
            raise ValueError("All orders must have the same invoice type")
        amount_total = sum(self.mapped("amount_total"))
        amount_tax = sum(self.mapped("amount_tax"))
        if amount_total >= 0:
            if invoice_types[0] == 'factura':
                if amount_tax == 0:
                    vals.update({
                        'l10n_latam_document_type_id': self.env.ref('l10n_cl.dc_y_f_dte').id,
                    })
                else:
                    vals.update({
                        'l10n_latam_document_type_id': self.env.ref('l10n_cl.dc_a_f_dte').id,
                    })
            elif invoice_types[0] == 'boleta':
                if amount_tax == 0:
                    vals.update({
                        'l10n_latam_document_type_id': self.env.ref('l10n_cl.dc_b_e_dte').id,
                    })
                else:
                    vals.update({
                        'l10n_latam_document_type_id': self.env.ref('l10n_cl.dc_b_f_dte').id,
                    })
        else:
            #Document type for refunds
            vals.update({
                'l10n_latam_document_type_id': self.env.ref('l10n_cl.dc_nc_f_dte').id,
            })

        return vals

    def _create_invoice(self, move_vals):
        move = super()._create_invoice(move_vals)
        if self.env.company.country_code == 'CL':
            if move.reversed_entry_id:
                reversed_move_id = self.env['account.move'].browse(move.reversed_entry_id.id)
                refunded_order_id = self.env['pos.order'].search([('account_move', '=', move.reversed_entry_id.id)], limit=1)
                refunded_order_order_lines_ids = self.env['pos.order.line'].search([('order_id', '=', refunded_order_id.id)])
                refunded_order_order_lines_set = set()
                for order_line in refunded_order_order_lines_ids:
                    refunded_order_order_lines_set.add((order_line.id, order_line.qty))
                refunded_order_lines_set = set()
                order_lines_ids = self.env['pos.order.line'].search([('order_id', '=', self.id)])
                for order_line in order_lines_ids:
                    refunded_order_lines_set.add((order_line.refunded_orderline_id.id, -order_line.qty))
                reference_doc_code = '3'
                if refunded_order_order_lines_set == refunded_order_lines_set:
                    reference_doc_code = '1'

                self.env['l10n_cl.edi.reference'].create({
                    'move_id': move.id,
                    'origin_doc_number': reversed_move_id.l10n_latam_document_number,
                    'l10n_cl_reference_doc_type_id': reversed_move_id.l10n_latam_document_type_id.id,
                    'reference_doc_code': reference_doc_code,
                    'reason': 'Anulación NC por aceptación con reparo (' + reversed_move_id.l10n_latam_document_number + ')',
                    'date': move.date,
                })
        return move

    def read_pos_data(self, data, config):
        result = super().read_pos_data(data, config)
        if not len(self):
            return result

        order_country = self[0].session_id.company_id.country_code
        if order_country != "CL":
            return result

        if len(self.filtered(lambda order: order.state in ['paid', 'invoiced'])) > 0:
            result['account_move'] = self.env['account.move']._load_pos_data_read(self.account_move, config)
            result['l10n_latam.document.type'] = self.env['l10n_latam.document.type']._load_pos_data_read(self.account_move.l10n_latam_document_type_id, config)
        return result
