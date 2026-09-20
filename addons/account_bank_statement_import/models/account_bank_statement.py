# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

from markupsafe import Markup

import logging
_logger = logging.getLogger(__name__)


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    # Ensure transactions can be imported only once (if the import format provides unique transaction ids)
    unique_import_id = fields.Char(string='Import ID', readonly=True, copy=False)

    _unique_import_id = models.Constraint(
        'unique (unique_import_id)',
        "A bank account transactions can be imported only once!",
    )

    @api.model
    def get_import_templates(self):
        return [{
            'label': _('Import Template for Bank Statement Lines'),
            'template': '/account_bank_statement_import/static/xls/bank_statement_line_import_template.xlsx'
        }]

    def _action_open_bank_reconciliation_widget(self, extra_domain=None, default_context=None, name=None, kanban_first=True):
        res = super()._action_open_bank_reconciliation_widget(extra_domain, default_context, name, kanban_first)
        res['help'] = Markup("<p class='o_view_nocontent_smiling_face'>{}</p><p>{}<br/>{}</p>").format(
            _('Nothing to do here!'),
            _('No transactions matching your filters were found.'),
            _('Click "New" or upload a %s.', ", ".join(self.env['account.journal']._get_bank_statements_available_import_formats())),
        )
        return res
