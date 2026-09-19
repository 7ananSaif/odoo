# Part of Odoo. See LICENSE file for full copyright and licensing details.

import io

from odoo import _
from odoo.http import Controller, request, route, content_disposition


class SaleCommissionTargetExportController(Controller):
    @route('/sale_commission/export/targets/<int:plan_id>', type='http', auth='user', readonly=True)
    def export_targets(self, plan_id):
        plan = request.env['sale.commission.plan'].browse(plan_id)
        target_ids = plan.target_commission_ids
        headers = [_("Performance"), _("Commission"), _("Currency")]
        return self._generate_xlsx(filename=plan.name, target_ids=target_ids, headers=headers)

    def _interpolate_target(self, target_rate, sorted_rates, values_by_rate):
        """Linear interpolation of the target value according to existing targets
        For two known targets values t1 and t2 having respontively x1 and x2 rate and
        y1 and y2 commission amounts, an intermediate t3 target  at 'target_rate'
        position (x) will have the following amount (y)
        y = a * target_rate + y1 where a is the slope.
        a = (y2-y1)/(x2-x1)
        """
        for rate in sorted_rates:
            if rate > target_rate:
                x2 = rate
                # all rate have a defined row
                y2 = values_by_rate[rate][1]
                break
            # previous values
            x1 = rate
            # all rate have a defined row
            y1 = values_by_rate[rate][1]
        if x1 is None or x2 is None or x2 == x1:
            return 0
        # y = b + ax
        amount = y1 + (y2 - y1) / (x2 - x1) * (target_rate - x1)
        return amount

    def _generate_rows(self, target_ids):
        """ Generate a xls file containing a table with a line for every 10% of target completion
        and the commission amount. Starting at 0% and ending with the last target level
        """
        if not target_ids:
            return []
        rows = []
        values_by_rate = {}
        sorted_rates = []
        currency_name = target_ids[0].currency_id.name
        for target in target_ids.sorted('target_rate'):
            row = [target.target_rate * 100, target.amount, currency_name]
            values_by_rate[target.target_rate] = row
            sorted_rates.append(target.target_rate)
            rows.append(row)
        target_max = target.target_rate + 0.1
        all_rate = [x / 100 for x in range(0, int(target_max * 100), 10) if x / 100 <= target.target_rate] + sorted_rates
        all_rate = set(all_rate)
        all_rate = sorted(all_rate)
        all_rows = []
        for target_val in all_rate:
            row_val = values_by_rate.get(target_val)
            if not row_val:
                amount = self._interpolate_target(target_val, sorted_rates, values_by_rate)
                row_val = [target_val * 100, amount, currency_name]
            all_rows.append(row_val)
        return all_rows

    def _generate_xlsx(self, filename="", target_ids=None, headers=None):
        buffer = io.BytesIO()
        import xlsxwriter  # noqa: PLC0415
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()
        worksheet.write_row(0, 0, headers)
        rows = self._generate_rows(target_ids)
        column_widths = [len(header) for header in headers]
        for row_idx, row in enumerate(rows, start=1):
            worksheet.write_row(row_idx, 0, row)
            for col_idx, cell_value in enumerate(row):
                column_widths[col_idx] = max(column_widths[col_idx], len(str(cell_value)))
        for col_idx, width in enumerate(column_widths):
            worksheet.set_column(col_idx, col_idx, width)
        workbook.close()
        content = buffer.getvalue()
        buffer.close()
        headers = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition(f'Targets - {filename}.xlsx'))
        ]
        return request.make_response(content, headers)
