# Part of Odoo. See LICENSE file for full copyright and licensing details.
import io

from odoo import _, fields, models
from odoo.fields import Domain


class L10n_ThTaxReportHandler(models.AbstractModel):
    _name = 'l10n_th.tax.report.handler'
    _inherit = ["account.generic.tax.report.handler"]
    _description = "Thai Tax Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        if self.env.company.account_fiscal_country_id.code == 'TH':
            options.setdefault('buttons', []).extend((
                {
                    'name': _('Sales Tax Report (xlsx)'),
                    'action': 'export_file',
                    'action_param': 'l10n_th_print_sale_tax_report',
                    'sequence': 82,
                    'file_export_type': _('Sales Tax Report (xlsx)')
                },
                {
                    'name': _('Purchase Tax Report (xlsx)'),
                    'action': 'export_file',
                    'action_param': 'l10n_th_print_purchase_tax_report',
                    'sequence': 83,
                    'file_export_type': _('Purchase Tax Report (xlsx)')
                }
            ))

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        return []

    def l10n_th_print_sale_tax_report(self, options):
        report = self.env['account.report'].browse(options['report_id'])
        base_tags = self.env['account.account.tag']._get_tax_tags('1. Sales amount', report.country_id.id)
        tax_tags = self.env['account.account.tag']._get_tax_tags('5. Output tax', report.country_id.id)
        data = self._generate_data(base_tags, tax_tags, 'sale', options)
        return {
            "file_name": _("Sales Tax Report"),
            "file_content": data,
            "file_type": "xlsx",
        }

    def l10n_th_print_purchase_tax_report(self, options):
        report = self.env['account.report'].browse(options['report_id'])
        base_tags = self.env['account.account.tag']._get_tax_tags('6. Purchase amount that is entitled to deduction of input tax from output tax in tax computation', report.country_id.id)
        tax_tags = self.env['account.account.tag']._get_tax_tags('7. Input tax (according to invoice of purchase amount in 6.)', report.country_id.id)
        data = self._generate_data(base_tags, tax_tags, 'purchase', options)
        return {
            "file_name": _("Purchase Tax Report"),
            "file_content": data,
            "file_type": "xlsx",
        }

    def _generate_data(self, base_tags, tax_tags, origin_type, options):
        # Dates are taken from the report options
        date_from = options['date'].get('date_from')
        date_to = options['date'].get('date_to')
        # We find the related move lines based on the report options and provided tags.
        domain = Domain.AND((
            self.env.ref('account.generic_tax_report')._get_options_domain(options, 'strict_range'),
            Domain('tax_tag_ids', 'in', (base_tags | tax_tags).ids),
        ))
        move_lines_per_move = self.env['account.move.line'].search(domain).grouped('move_id')

        file_data = io.BytesIO()
        import xlsxwriter  # noqa: PLC0415
        workbook = xlsxwriter.Workbook(file_data, {
            'in_memory': True,
        })
        sheet = workbook.add_worksheet()

        currency_default_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'num_format': '฿#,##0.00'})
        date_default_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'num_format': 'dd/mm/yyyy'})
        default_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10})
        title_style = workbook.add_format({'font_name': 'Arial', 'font_size': 18, 'bold': True, 'align': 'center'})
        center_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'align': 'center'})
        col_header_style = workbook.add_format(
            {'font_name': 'Arial', 'font_size': 10, 'bold': True, 'bg_color': '#d9d9d9'})

        sheet.set_column(0, 0, 4)
        sheet.set_column(1, 1, 15.2)
        sheet.set_column(2, 2, 11.2)
        sheet.set_column(3, 3, 16)
        sheet.set_column(4, 4, 15.2)
        sheet.set_column(5, 5, 19.2)
        sheet.set_column(6, 7, 14)

        y_offset = 0

        title_dict = {'sale': _('Sales Tax Report'), 'purchase': _('Purchase Tax Report')}
        title = title_dict.get(origin_type, _('Tax Report'))
        sheet.merge_range(y_offset, 0, y_offset, 9, title, title_style)
        y_offset += 1

        date_from = fields.Date.to_date(date_from).strftime('%d/%m/%Y')
        date_to = fields.Date.to_date(date_to).strftime("%d/%m/%Y")
        date = _("From %(date_from)s to %(date_to)s", date_from=date_from, date_to=date_to)
        company = self.env.company
        company_name = company.name
        vat = company.vat or ''

        infos = [date, company_name, vat, company.partner_id.l10n_th_branch_name]
        for info in infos:
            sheet.merge_range(y_offset, 0, y_offset, 9, info, center_style)
            y_offset += 1
        y_offset += 1

        sheet.set_row(y_offset, 32.7)
        headers = [_("No."), _("Tax Invoice No."), _("Reference"), _("Invoice Date"), _("Contact Name"),
                   _("Tax ID"), _("Company Information"), _("Total Amount"), _("Total Excluding VAT Amount"), _("Vat Amount")]
        for index, header in enumerate(headers):
            sheet.write(y_offset, index, header, col_header_style)
        y_offset += 1

        accumulate_total = 0
        accumulate_untaxed_signed = 0
        accumulate_tax = 0

        for index, (move, move_lines) in enumerate(move_lines_per_move.items()):
            base_lines_per_tag = {}
            tax_lines_per_tag = {}
            for line in move_lines:
                for tag in base_tags:
                    if tag in line.tax_tag_ids:
                        base_lines_per_tag.setdefault(tag, []).append(line)
                for tag in tax_tags:
                    if tag in line.tax_tag_ids:
                        tax_lines_per_tag.setdefault(tag, []).append(line)

            total_base = total_tax = 0
            # Sum the base lines
            for base_tag_id, base_lines in base_lines_per_tag.items():
                balance_negate = -1 if base_tag_id.balance_negate else 1
                for line in base_lines:
                    total_base += line.balance * balance_negate
            # Repeat that for the tax lines
            for tax_tag_id, tax_lines in tax_lines_per_tag.items():
                balance_negate = -1 if tax_tag_id.balance_negate else 1
                for line in tax_lines:
                    total_tax += line.balance * balance_negate
            # Get the amount including taxes
            total = total_base + total_tax

            sheet.write(y_offset, 0, index + 1, default_style)
            sheet.write(y_offset, 1, move.name, default_style)
            sheet.write(y_offset, 2, move.ref or '', default_style)
            sheet.write(y_offset, 3, move.date, date_default_style)
            # If no partner is provided:
            # (4) In other cases, such as a simplified tax invoice, fill in “Selling goods or providing services”
            sheet.write(y_offset, 4, move.partner_id.name or _('Selling goods or providing services'), default_style)
            sheet.write(y_offset, 5, move.partner_id.vat or '', default_style)
            sheet.write(y_offset, 6, move.partner_id.l10n_th_branch_name or '', default_style)
            sheet.write(y_offset, 7, total, currency_default_style)
            sheet.write(y_offset, 8, total_base, currency_default_style)
            sheet.write(y_offset, 9, total_tax, currency_default_style)
            accumulate_total += total
            accumulate_untaxed_signed += total_base
            accumulate_tax += total_tax
            y_offset += 1
        y_offset += 1
        y_offset += 1

        sheet.write(y_offset, 6, "Total", default_style)
        sheet.write(y_offset, 7, accumulate_total, currency_default_style)
        sheet.write(y_offset, 8, accumulate_untaxed_signed, currency_default_style)
        sheet.write(y_offset, 9, accumulate_tax, currency_default_style)
        y_offset += 1

        workbook.close()
        file_data.seek(0)
        data = file_data.read()

        return data
