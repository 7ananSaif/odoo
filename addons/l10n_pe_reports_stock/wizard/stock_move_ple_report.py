import base64
from collections import defaultdict
import csv
import re

from dateutil.relativedelta import relativedelta
from io import StringIO
from werkzeug.urls import url_encode

from odoo import api, fields, models
from odoo.fields import Date, Domain
from odoo.exceptions import UserError


class L10n_PeStockPleWizard(models.TransientModel):
    _name = 'l10n_pe.stock.ple.wizard'
    _description = 'Wizard to generate Stock Move PLE reports for PE'

    @api.model
    def default_get(self, fields):
        results = super().default_get(fields)
        if self.env.company.country_code != 'PE':
            raise UserError(self.env._('This option is only available for Peruvian companies.'))
        date_from = Date.today().replace(day=1)
        results['date_from'] = date_from
        results['date_to'] = date_from + relativedelta(months=1, days=-1)
        return results

    date_from = fields.Date(
        required=True,
        help="Choose a date from to get the PLE reports at that date",
    )
    date_to = fields.Date(
        required=True,
        help="Choose a date to get the PLE reports at that date",
    )
    report_data = fields.Binary('Report file', readonly=True, attachment=False)
    report_filename = fields.Char(string='Filename', readonly=True)
    mimetype = fields.Char(string='Mimetype', readonly=True)

    def get_ple_report_12_1(self):
        return self.get_ple_report('1201')

    def get_ple_report_13_1(self):
        return self.get_ple_report('1301')

    def get_ple_report(self, report_number):
        data = self._get_ple_report_content(report_number)
        has_data = "1" if data else "0"
        filename = "LE%s%s%02d00%s00001%s11.txt" % (
            self.env.company.vat, self.date_from.year, self.date_from.month, report_number, has_data)
        self.write({
            'report_data': base64.b64encode(data.encode()),
            'report_filename': filename,
            'mimetype': 'application/txt',
        })
        return {
            'type': 'ir.actions.act_url',
            'url':  '/web/content/?' + url_encode({
                'model': self._name,
                'id': self.id,
                'filename_field': 'report_filename',
                'field': 'report_data',
                'download': 'true'
            }),
            'target': 'new'
        }

    @api.model
    def _get_serie_folio(self, number):
        values = {"serie": "", "folio": ""}
        number_matchs = list(re.finditer("\\d+", number or ""))
        if number_matchs:
            last_number_match = number_matchs[-1]
            values["serie"] = number[: last_number_match.start()].replace("-", "") or ""
            values["folio"] = last_number_match.group() or ""
        return values

    def _get_ple_report_content(self, report):
        def _get_stock_valuation(category):
            cost_method = self.env['product.category'].browse(category).property_cost_method
            return {'average': '1', 'fifo': '2', 'standard': '3'}.get(cost_method, '')

        data = []
        period = '%s%s00' % (self.date_from.year, str(self.date_from.month).zfill(2))
        moves = self._get_ple_reports_data()
        count = 0
        products = []
        delivery_number = 'l10n_latam_document_number' in self.env['stock.picking']._fields
        for move in moves:
            # Only consider the first line.
            # If an entry was invoiced in 2 or more records, only get the values from the first invoice
            product = move.product_id
            product_tmpl = product.product_tmpl_id
            invoice = move.sale_line_id.invoice_lines.move_id[:1]
            bill = move.purchase_line_id.invoice_lines.move_id[:1]
            serie_folio = self._get_serie_folio((move.picking_id.l10n_latam_document_number if delivery_number and move.picking_id.l10n_latam_document_number else (invoice.name or bill.name or bill.name)) or '')
            date = (invoice.invoice_date or bill.invoice_date or move.date).strftime('%d/%m/%Y') if (invoice.invoice_date or bill.invoice_date or move.date) else ''
            document_type = invoice.l10n_latam_document_type_id or bill.l10n_latam_document_type_id
            if move.product_id.id not in products:
                valuation_data = self._append_valuation_line(move, period, count, report)
                products.append(move.product_id.id)
                if valuation_data:
                    data.append(valuation_data)
                    count += 1
            values = {
                'period': period,
                'cuo': str(count).zfill(6),
                'number': 'M1',  # The first digit should be 'M' to denote entries for movements or adjustments within the month. Therefore, 'M1' indicates this is the first such entry.
                'establishment': move.warehouse_id.l10n_pe_anexo_establishment_code or '0000',
                'catalogue': '1',  # Only supported 1 because We use Unspsc
                'type_of_existence': (product_tmpl.l10n_pe_type_of_existence or '99').zfill(2),
                'default_code': (product.default_code or '').replace('_', '')[:24],
                'catalogue_used': '1',  # Only supported 1 because We use Unspsc
                'unspsc': product_tmpl.unspsc_code_id.code or '',
                'date': date,
                'document_type': document_type.code or '00',
                'serie': serie_folio['serie'].replace(' ', '').replace('/', '') or '0',
                'folio': serie_folio['folio'].replace(' ', '') or '0',
                'operation_type': (move.picking_id.l10n_pe_operation_type or '99').zfill(2),
                'product': product.name,
                'uom': move.product_uom.l10n_pe_edi_measure_unit_code,
            }
            count += 1
            if report == '1201':
                quantity = move.product_uom._compute_quantity(move.quantity, move.product_uom)
                values.update({
                    'qty_in': quantity if move.is_in else '0.00',
                    'qty_out': -quantity if move.is_out else '0.00',
                    'state': '1',
                })
                data.append(values)
                continue
            values.update({
                'valuation': _get_stock_valuation(product_tmpl.category_id.id),
                'qty_in': move._get_valued_qty() if move.is_in else '0.00',
                'cost_in': move._get_price_unit() if move.is_in else '0.00',
                'value_in': move.value if move.is_in else '0.00',
                'qty_out': move._get_valued_qty() if move.is_out else '0.00',
                'cost_out': move._get_price_unit() if move.is_out else '0.00',
                'value_out': move.value if move.is_out else '0.00',
                'remaining': abs(move.remaining_qty),
                'unit_cost_final': abs((move.remaining_value) / (move.remaining_qty or 1)) or '0.00',
                'value': abs(move.remaining_value),
                'state': '1',
            })
            data.append(values)
        data.extend(self._append_historic_valuation_lines(products, period, count, report))
        if not data:
            return ''
        csv.register_dialect("pipe_separator", delimiter="|", skipinitialspace=True, lineterminator='|\n')
        output = StringIO()
        writer = csv.DictWriter(output, dialect="pipe_separator", fieldnames=data[0].keys())
        writer.writerows(data)
        txt_result = output.getvalue()
        return txt_result

    def _append_valuation_line(self, move, period, count, report):
        def _get_stock_valuation(category):
            cost_method = self.env['product.category'].browse(category).property_cost_method
            return {'average': '1', 'fifo': '2', 'standard': '3'}.get(cost_method, '')
        quantity = move.product_id.with_context(to_date=self.date_from).qty_available
        if not quantity:
            return {}
        invoice = move.sale_line_id.invoice_lines.move_id[:1]
        bill = move.purchase_line_id.invoice_lines.move_id[:1]
        values = {
            'period': period,
            'cuo': str(count).replace('/', '').zfill(6),
            'number': 'A1',  # The first digit should be 'M' to denote entries for movements or adjustments within the month. Therefore, 'M1' indicates this is the first such entry.
            'establishment': move.warehouse_id.l10n_pe_anexo_establishment_code or '0000',
            'catalogue': '1',  # Only supported 1 because We use Unspsc
            'type_of_existence': (move.product_id.product_tmpl_id.l10n_pe_type_of_existence or '99').zfill(2),
            'default_code': (move.product_id.default_code or '').replace('_', '')[:24],
            'catalogue_used': '1',  # Only supported 1 because We use Unspsc
            'unspsc': move.product_id.product_tmpl_id.unspsc_code.code,
            'date': self.date_from.strftime('%d/%m/%Y'),
            'document_type': invoice.l10n_latam_document_type_id.code or bill.l10n_latam_document_type_id.code or '00',
            'serie': '0',
            'folio': '0',
            'operation_type': '16',
            'product': move.product_id.with_lang('en_US').name,
            'uom': move.product_uom.l10n_pe_edi_measure_unit_code,
        }
        count += 1
        if report == '1201':
            values.update({
                'qty_in': quantity if quantity > 0 else '0.00',
                'qty_out': '0.00',
                'state': '1',
            })
            return values
        unit_cost = move._get_price_unit() or '0.00'
        values.update({
            'valuation': _get_stock_valuation(move.product_id.category_id.id),
            'qty_in': quantity if quantity > 0 else '0.00',
            'cost_in': unit_cost,
            'value_in': (quantity * float(unit_cost)) or '0.00',
            'qty_out': '0.00',
            'cost_out': '0.00',
            'value_out': '0.00',
            'remaining': quantity if quantity > 0 else '0.00',
            'unit_cost_final': unit_cost,
            'value': (quantity * float(unit_cost)) or '0.00',
            'state': '1',
        })
        return values

    def _append_historic_valuation_lines(self, products, period, count, report):
        def _get_stock_valuation(category_id):
            cost_method = self.env['product.category'].browse(category_id).property_cost_method
            return {'average': '1', 'fifo': '2', 'standard': '3'}.get(cost_method, '')

        domain = Domain([
            ('company_id', '=', self.env.company.id),
            ('product_id', 'not in', products),
            ('date', '<', self.date_from),
        ])
        moves_in = self.env['stock.move']._read_group(
            domain & Domain([('is_in', '=', True)]),
            ['product_id', 'product_uom'],
            ['value:sum', 'quantity:sum'],
        )
        moves_out = self.env['stock.move']._read_group(
            domain & Domain([('is_out', '=', True)]),
            ['product_id', 'product_uom'],
            ['value:sum', 'quantity:sum'],
        )

        value_by_product = defaultdict(float)
        qty_by_product = defaultdict(float)
        for product, uom, value, qty in moves_in:
            if uom != product.uom_id:
                qty = uom._compute_quantity(qty, product.uom_id)
            value_by_product[product] = value
            qty_by_product[product] = qty
        for product, uom, value, qty in moves_out:
            if uom != product.uom_id:
                qty = uom._compute_quantity(qty, product.uom_id)
            value_by_product[product] -= value
            qty_by_product[product] -= qty
        data = []
        for product, value in self.env.cr.dictfetchall():
            quantity = qty_by_product[product]
            if quantity <= 0:
                continue
            values = {
                'period': period,
                'cuo': str(count).zfill(6),
                'number': 'A1',  # The first digit should be 'M' to denote entries for movements or adjustments within the month. Therefore, 'M1' indicates this is the first such entry.
                'establishment': '0000',
                'catalogue': '1',  # Only supported 1 because We use Unspsc
                'type_of_existence': (product.product_tmpl_id.l10n_pe_type_of_existence or '99').zfill(2),
                'default_code': (product.default_code or '').replace('_', '')[:24],
                'catalogue_used': '1',  # Only supported 1 because We use Unspsc
                'unspsc': product.product_tmpl_id.unspsc_code_id.code,
                'date': self.date_from.strftime('%d/%m/%Y'),
                'document_type': '00',
                'serie': '0',
                'folio': '0',
                'operation_type': '16',
                'product': product.with_lang('en_US').name,
                'uom': product.uom_id.l10n_pe_edi_measure_unit_code,
            }
            count += 1
            if report == '1201':
                values.update({
                    'qty_in': quantity,
                    'qty_out': '0.00',
                    'state': '1',
                })
                data.append(values)
                continue
            unit_cost = product.standard_price if product.standard_price > 0 else '0.00'
            values.update({
                'valuation': _get_stock_valuation(product.category_id.id),
                'qty_in': quantity if quantity > 0 else '0.00',
                'cost_in': unit_cost,
                'value_in': (quantity * float(unit_cost)) or '0.00',
                'qty_out': '0.00',
                'cost_out': '0.00',
                'value_out': '0.00',
                'remaining': quantity if quantity > 0 else '0.00',
                'unit_cost_final': unit_cost,
                'value': (quantity * float(unit_cost)) or '0.00',
                'state': '1',
            })
            data.append(values)
        return data

    def _get_ple_reports_data(self):
        domain = [
            ('state', '=', 'done'),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('company_id', '=', self.env.company.id),
            '|',
            ('location_id.usage', 'in', ('supplier', 'customer', 'inventory', 'production')),
            ('location_dest_id.usage', 'in', ('supplier', 'customer', 'inventory', 'production')),
        ]

        return self.env['stock.move'].sudo().search(domain, order="product_id.id, date, id desc")
