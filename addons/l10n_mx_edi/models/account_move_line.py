from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_mx_edi_tax_object = fields.Selection(
        string="Tax Object",
        selection=[
            ('01', "01 - No tax Object"),
            ('02', "02 - Tax Object"),
            ('03', "03 - Tax Object and doesn't require breakdown"),
            ('04', "04 - Tax Object and doesn't have tax"),
            ('05', "05 - Tax Object, VAT for PODEBI"),
            ('06', "06 - VAT Object, No VAT forwarded"),
            ('07', "07 - No VAT forwarded, IEPS breakdown"),
            ('08', "08 - No VAT forwarded, No IEPS breakdown"),
        ],
        compute='_compute_l10n_mx_edi_tax_object',
        store=True,
        readonly=False,
    )

    @api.depends('tax_ids', 'move_id.company_id', 'move_id.l10n_mx_edi_cfdi_to_public', 'move_id.l10n_mx_edi_is_cfdi_needed', 'move_id.partner_id')
    def _compute_l10n_mx_edi_tax_object(self):
        L10nMxEdiDocument = self.env['l10n_mx_edi.document']
        for move, lines in self.grouped('move_id').items():
            lines.l10n_mx_edi_tax_object = None
            if not move._l10n_mx_edi_is_cfdi_invoice():
                continue

            invoice_lines = move._l10n_mx_edi_cfdi_invoice_line_ids()
            cfdi_values = L10nMxEdiDocument._get_company_cfdi_values(move.company_id)
            L10nMxEdiDocument._add_customer_cfdi_values(cfdi_values, customer=move.partner_id, to_public=move.l10n_mx_edi_cfdi_to_public)
            base_lines = [
                move._prepare_product_base_line_for_taxes_computation(line)
                for line in lines
                if line in invoice_lines
            ]
            L10nMxEdiDocument._add_tax_objected_cfdi_values(cfdi_values, base_lines)
            for base_line in base_lines:
                base_line['record'].l10n_mx_edi_tax_object = base_line['tax_objected']

    def _l10n_mx_edi_get_cfdi_line_name(self):
        self.ensure_one()
        if self.product_id.display_name:
            if self.name:
                if self.product_id.display_name in self.name or self.name in self.product_id.display_name:
                    return self.name
                return f"{self.product_id.display_name} {self.name}"
            return self.product_id.display_name
        return self.name

    def _get_product_unspsc_code(self):
        self.ensure_one()

        return (
            "84111506"
            if self in self._get_downpayment_lines()
            else self.product_id.unspsc_code_id.code
        )

    def _get_uom_unspsc_code(self):
        self.ensure_one()

        return (
            "ACT"
            if self in self._get_downpayment_lines()
            else self.product_uom_id.unspsc_code_id.code
        )

    def _filter_aml_lot_valuation(self):
        # EXTENDS account
        return super()._filter_aml_lot_valuation() and not self.move_id.l10n_mx_edi_cfdi_cancel_id
