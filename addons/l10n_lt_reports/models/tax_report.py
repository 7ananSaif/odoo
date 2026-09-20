from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import RedirectWarning
from odoo.tools import cleanup_xml_node, float_repr, SQL


class LithuanianTaxReportHandler(models.AbstractModel):
    """
    Handler for generating the I.SAF xml
    """
    _name = 'l10n_lt.tax.report.handler'
    _inherit = 'account.tax.report.handler'
    _description = 'Lithuanian Tax Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        options.setdefault('buttons', []).append({
            'name': 'I.SAF',
            'sequence': 30,
            'action': 'export_file',
            'action_param': 'export_tax_report_to_xml',
            'file_export_type': 'XML',
        })

    @api.model
    def _l10n_lt_get_all_move_values(self, report, options):
        """
        Get all values of bills and invoices, used to generate the i.SAF xml export.

        There may be a lot of lines for a period. So we do a single query that will get all the values in the format
        we want, to avoid looping and doing more heavy computation line per line in Python.
        """
        query = report._get_report_query(options, 'strict_range')
        query = SQL(
            '''
        WITH tax_amounts_details AS (
        -- The amounts need to be grouped by tax, with base amount and tax amount for each.
        -- To do so, we group all tax amounts by tax and move, which we lateral join to associate the base amounts
            SELECT SUM(account_move_line.balance) * CASE WHEN account_move_line__move_id.move_type IN %(inbound_types)s THEN 1 ELSE -1 END AS base_amount,
                   MIN(tax_amounts.tax_amount) as tax_amount,
                   account_tax.l10n_lt_tax_code,
                   account_tax.amount as percentage,
                   account_move_line__move_id.id
              FROM %(table_references)s
              JOIN account_move_line_account_tax_rel ON account_move_line_account_tax_rel.account_move_line_id = account_move_line.id
              JOIN account_tax ON account_tax.id = account_move_line_account_tax_rel.account_tax_id
         LEFT JOIN LATERAL (
                     SELECT SUM(tax_aml.balance) * CASE WHEN account_move_line__move_id.move_type IN %(inbound_types)s THEN 1 ELSE -1 END AS tax_amount
                       FROM account_move_line tax_aml
                      WHERE tax_aml.tax_line_id = account_tax.id
                        AND tax_aml.move_id = account_move_line__move_id.id
                   GROUP BY account_tax.id, account_move_line__move_id.id
                   ) as tax_amounts ON TRUE
             WHERE %(search_condition)s
          GROUP BY account_tax.id, account_move_line__move_id.id
        )
        SELECT account_move_line__move_id.name,
               account_move_line__move_id.date,
               res_partner.id AS partner_id,
               res_partner.vat as partner_vat,
               res_partner.company_registry as registration_number,
               res_country.code as country_code,
               res_partner.name AS partner_name,
               res_partner.company_registry AS partner_registration_number,
               account_move_line__move_id.invoice_date,
               account_move_line__move_id.move_type,
               reversed_move.invoice_date AS reversed_move_invoice_date,
               reversed_move.name AS reversed_move_name,
               account_move_line__move_id.date AS registration_account_date,
               account_move_line__move_id.delivery_date,
               jsonb_agg(DISTINCT jsonb_build_object(
                   'percentage', tax_amounts_details.percentage,
                   'tax_amount', tax_amounts_details.tax_amount,
                   'tax_code', tax_amounts_details.l10n_lt_tax_code,
                   'base_amount', tax_amounts_details.base_amount
               )) as tax_total
          FROM %(table_references)s
          JOIN res_partner ON account_move_line__move_id.partner_id = res_partner.id
     LEFT JOIN res_country ON res_partner.country_id = res_country.id
     LEFT JOIN account_move reversed_move ON account_move_line__move_id.reversed_entry_id = reversed_move.id
          JOIN tax_amounts_details ON tax_amounts_details.id = account_move_line__move_id.id
         WHERE %(search_condition)s
      GROUP BY account_move_line__move_id.id, res_partner.id, reversed_move.id, res_country.code;
            ''',
            inbound_types=tuple(self.env['account.move'].get_inbound_types()),
            table_references=query.from_clause,
            search_condition=query.where_clause,
        )
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    @api.model
    def export_tax_report_to_xml(self, options):
        """ Generates the iSAF XML file """
        if not self.env.company.vat:
            action = self.env.ref('base.action_res_company_form')
            raise RedirectWarning(_('Please define the VAT on your company.'), action.id, _('Company Settings'))

        report = self.env['account.report'].browse(options['report_id'])
        move_vals = self._l10n_lt_get_all_move_values(report, options)
        invoice_vals = [
            move_val
            for move_val in move_vals
            if move_val.get('move_type') in self.env['account.move'].get_sale_types(include_receipts=True)
        ]
        bill_vals = [
            move_val
            for move_val in move_vals
            if move_val.get('move_type') in self.env['account.move'].get_purchase_types(include_receipts=True)
        ]

        values = {
            'file_version': 'iSAF1.2',
            'today_str': fields.Datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            'registration_number': self.env.company.company_registry,
            'date_from': options['date']['date_from'],
            'date_to': options['date']['date_to'],
            'float_repr': float_repr,
            'bill_vals': bill_vals,
            'invoice_vals': invoice_vals,
        }
        date_from = fields.Date.from_string(options['date']['date_from'])
        audit_content = self.env['ir.qweb']._render('l10n_lt_reports.iSAF_template', values)
        return {
            'file_name': f'iSAF_{date_from.month}_{date_from.year}.xml',
            'file_content': etree.tostring(cleanup_xml_node(audit_content, remove_blank_nodes=False)),
            'file_type': 'xml',
        }
