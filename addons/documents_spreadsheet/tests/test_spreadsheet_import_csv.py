import json

from odoo.tests.common import HttpCase

from .common import SpreadsheetTestCommon
from odoo.tools import file_open, mute_logger


class SpreadsheetImportCSV(HttpCase, SpreadsheetTestCommon):
    def test_import_csv(self):
        folder = self.env["documents.document"].create({"name": "New folder", "type": "folder"})
        with file_open('documents_spreadsheet/tests/data/test.csv', 'rb') as f:
            document_csv = self.env['documents.document'].create({
                'raw': f.read(),
                'name': 'test.csv',
                'mimetype': 'text/csv',
                'folder_id': folder.id
            })
            with mute_logger('odoo.addons.documents.models.documents_document'):  # Creating document(s) as superuser
                spreadsheet_id = document_csv.import_to_spreadsheet()
            spreadsheet = self.env["documents.document"].browse(spreadsheet_id).exists()
            self.assertTrue(spreadsheet)
            self.assertEqual(spreadsheet.name, "test")
            expected_data = {
                "sheets": [
                    {
                        "cells": {
                            "A1": "1",
                            "B1": "Pamella",
                            "C1": "Piercy",
                            "D1": "ppiercy0@slashdot.org",
                            "A2": "2",
                            "B2": "Crissie",
                            "C2": "Narrie",
                            "D2": "cnarrie1@godaddy.com",
                            "A3": "3",
                            "B3": "Ruby",
                            "C3": "Smallcombe",
                            "D3": "rsmallcombe2@google.it",
                        },
                        "comments": {}
                    }
                ]
            }
            self.assertEqual(json.loads(spreadsheet.raw), expected_data)
