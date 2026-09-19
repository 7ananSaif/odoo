# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models
from odoo.tools import date_utils

# In terms of general calendar; in Australia q1 is from July and is equivalent to q2 here.
percentage_per_quarter = {
    1: 1,
    2: 0.25,
    3: 0.50,
    4: 0.75,
}


class BasReportsHandler(models.AbstractModel):
    _name = 'bas.reports.handler'
    _inherit = ['account.report.custom.handler']
    _description = 'BAS reports Custom Handler'

    def _report_custom_engine_quarter_percentage(self, expressions, options, date_scope, current_groupby, next_groupby, offset=0, limit=None, warnings=None):
        quarter = date_utils.get_quarter_number(fields.Date.from_string(options['date']['date_to']))
        return {
            'quarter': percentage_per_quarter.get(quarter, 1),
        }
