from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestAISources(TransactionCase):
    # tests the processing of rich spreadsheets indexed by `attachment_indexation`
    def _create_attachment(self, name, mimetype, content):
        with patch.object(self.registry['ir.attachment'], '_index', lambda self, data, _type: data):
            return self.env['ir.attachment'].create({
                'name': name,
                'mimetype': mimetype,
                'raw': content,
            })

    def test_multi_sheet_csv_with_headers(self):
        # Two sheets separated by blank line, both with headers
        index_content = b"Name,Age\nAlice,30\nBob,25\n\nProduct,Price\nPen,1.2\nNotebook,2.5"

        attachment = self._create_attachment('people_and_products.csv', 'text/csv', index_content)
        content = attachment._get_attachment_content()
        self.assertIsInstance(content, str)
        self.assertTrue(content)
        # Validate first sheet rows are parsed with explicit headers
        self.assertIn("{'Name': 'Alice', 'Age': '30'}", content)
        self.assertIn("{'Name': 'Bob', 'Age': '25'}", content)
        # Validate second sheet rows are parsed with explicit headers
        self.assertIn("{'Product': 'Pen', 'Price': '1.2'}", content)
        self.assertIn("{'Product': 'Notebook', 'Price': '2.5'}", content)

    def test_ragged_rows_extra_and_missing_columns(self):
        # CSV with header, rows having extra and missing columns
        # Row 2 has extra fields (captured under _extra_fields), row 3 has a missing value
        sheet = b'3,10\n1,2,3,4\n5\n6,7'

        attachment = self._create_attachment('ragged.csv', 'text/csv', sheet)
        content = attachment._get_attachment_content()
        self.assertIsInstance(content, str)
        self.assertTrue(content)
        # Extra fields captured under _extra_fields
        self.assertIn("'Column_0': '1'", content)
        self.assertIn("'Column_1': '2'", content)
        self.assertIn("'_extra_fields': ['3', '4']", content)
        # Missing column becomes None
        self.assertIn("{'Column_0': '5', 'Column_1': None}", content)
        # Normal row
        self.assertIn("{'Column_0': '6', 'Column_1': '7'}", content)
