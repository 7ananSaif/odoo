from odoo import models, modules


class SpreadsheetTest(models.Model):
    _inherit = 'spreadsheet.test'

    def action_open_spreadsheet(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'fake_action',
            'params': {
                'spreadsheet_id': self.id,
            }
        }

    def _get_spreadsheet_selector(self):
        if not modules.module.current_test:
            return None
        return {
            "model": self._name,
            "display_name": "Test spreadsheets",
            "sequence": 100,
        }
