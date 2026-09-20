import io
import xlsxwriter
from odoo import http, _
from odoo.http import request


class AssetTemplateController(http.Controller):

    @http.route('/web/binary/download_asset_template/<int:company_id>', type='http', auth='user')
    def download_template(self, company_id):
        """
        Handles the HTTP request and serves the generated Excel file for download.
        """
        content = self._generate_asset_import_template(company_id)

        return request.make_response(
            content,
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', 'attachment; filename="asset_import_template.xlsx"'),
            ]
        )

    def _get_technical_headers(self):
        """ Defines and returns the common functional and technical headers. """
        return [item[0] for item in self._get_instructions_data()]

    def _get_localized_example_data(self, current_company_id, env):
        """
        Dynamically fetches localized example values for accounts and journal
        based on the current company and generates multiple example rows.
        """
        current_company = env['res.company'].browse(current_company_id)

        def get_account_name_by_type(account_types):
            for acc_type in account_types:
                if account := env['account.account'].with_company(current_company).search([
                    *env['account.account']._check_company_domain(current_company),
                    ('account_type', '=', acc_type),
                ], limit=1):
                    return account.display_name if account.display_name.startswith(account.code) else f"{account.code} {account.display_name}"

            return ''

        def get_journal_name_by_type(journal_type):
            journal = env['account.journal'].with_company(current_company).search([
                *env['account.journal']._check_company_domain(current_company),
                ('type', '=', journal_type),
            ], limit=1)
            return journal.name or ''

        asset_account_example = get_account_name_by_type(['asset_fixed', 'asset_non_current'])
        depreciation_account_example = get_account_name_by_type(['asset_fixed', 'asset_non_current'])
        expense_account_example = get_account_name_by_type(['expense_depreciation', 'expense'])
        journal_example = get_journal_name_by_type('general')

        all_example_rows = [
            [
                'Computer 1', '800.00', '01-01-2025', '', 'Straight Line', '4', 'Years', '', 'No Prorata', '01-01-2025',
                '200.00', '0.00', current_company.name,
                asset_account_example, depreciation_account_example,
                expense_account_example, journal_example,
            ],
            [
                'Computer 2', '25000.00', '03-15-2025', '', 'Declining', '5', 'Years', '2', 'Based on days per period', '03-15-2025',
                '0.00', '2000.00', current_company.name,
                asset_account_example, depreciation_account_example,
                expense_account_example, journal_example,
            ],
            [
                'Machine A', '15000.00', '09-01-2024', '', 'Straight Line', '10', 'Years', '', 'Constant Periods', '09-01-2024',
                '1500.00', '500.00', current_company.name,
                asset_account_example, depreciation_account_example,
                expense_account_example, journal_example,
            ],
            [
                'Machine B', '100000.00', '06-20-2025', '', 'Straight Line', '60', 'Months', '', 'No Prorata', '06-20-2025',
                '10000.00', '10000.00', current_company.name,
                asset_account_example, depreciation_account_example,
                expense_account_example, journal_example,
            ]
        ]

        return all_example_rows

    def _get_instructions_data(self):
        """Defines and returns the data for the 'Instructions' sheet."""
        return [
            ('name', _('Asset Name'), True, _('Mandatory column. This is the name of the asset.')),
            ('original_value', _('Original Value'), True, _('The amount will be considered in company currency.')),
            ('acquisition_date', _('Acquisition Date'), True, _('e.g. 01-27-2025 (format: MM-DD-YYYY)')),
            ('asset_group_id', _('Asset Group'), False, _('Optional. The name or external ID of the asset group. Must exist in Odoo (e.g., Office Equipment, Vehicles, Machinery).')),
            ('method', _('Method'), True, _('e.g. Straight Line, Declining Balance. Determines how depreciation is calculated.')),
            ('method_number', _('Duration'), True, _('e.g. 3 for 3 years, or 12 for 12 months. It must be an integer representing the total number of periods.')),
            ('method_period', _('Months/Years'), True, _('Either "Months" or "Years" (case-insensitive). Specifies the unit of duration.')),
            ('method_progress_factor', _('Declining Factor'), False, _('Only applicable for Declining Balance method (e.g., 2 for double declining). Ignored for Straight Line.')),
            ('prorata_computation_type', _('Computation'), True, _('e.g. No Prorata, Constant Periods, Based on days per period. This determines how the first depreciation entry is calculated.')),
            ('prorata_date', _('Prorata Date'), True, _('Start date of the depreciation period. Should be in MM-DD-YYYY format. If left blank, it defaults to the acquisition date.')),
            ('already_depreciated_amount_import', _('Depreciated Amount'), False, _('The total amount of depreciation already recorded for the asset before import. This amount will be considered in company currency.')),
            ('salvage_value', _('Not Depreciable Value'), False, _('The estimated residual value of the asset at the end of its useful life. This amount will not be depreciated. Considered in company currency.')),
            ('company_id', _('Company'), True, _("Must match the selected company during import. Use the company's display name.")),
            ('account_asset_id', _('Fixed Asset Account'), True, _('The balance sheet account for the asset itself (e.g., "151000 Fixed Asset"). Must exist in Odoo and be of "Fixed Asset" or "Non-current Assets" type.')),
            ('account_depreciation_id', _('Depreciation Account'), True, _('The accumulated depreciation account (contra-asset account). Must exist in Odoo and be of "Fixed Asset" or "Non-current Assets" type.')),
            ('account_depreciation_expense_id', _('Expense Account'), True, _('The expense account for posting periodic depreciation entries (e.g., "630000 Depreciation Expenses"). Must exist in Odoo and be of "Depreciation" or "Expense" type.')),
            ('journal_id', _('Journal'), True, _('The code or name of the associated journal in Odoo for depreciation entries (e.g., MISC - Miscellaneous Operations, INV - Customer Invoices, BILL - Vendor Bills).')),
        ]

    def _write_asset_sheet(self, workbook, headers, all_example_rows):
        """
        Creates and populates the 'Assets' sheet with headers, multiple example data rows, and comments.
        """
        worksheet_assets = workbook.add_worksheet('Assets')
        header_format = workbook.add_format({'bold': True})

        for col, header in enumerate(headers):
            worksheet_assets.write(0, col, header, header_format)

        for row_idx, example_row in enumerate(all_example_rows, start=1):
            for col, example_value in enumerate(example_row):
                worksheet_assets.write(row_idx, col, example_value)

        for col, header in enumerate(headers):
            max_len = len(str(header))
            for example_row in all_example_rows:
                if col < len(example_row):
                    max_len = max(max_len, len(str(example_row[col])))
            worksheet_assets.set_column(col, col, max_len + 4)

    def _write_instructions_sheet(self, workbook, instructions_data):
        """
        Creates and populates the 'Instructions' sheet with column details and notes.
        """
        worksheet_instructions = workbook.add_worksheet('Instructions')

        instruction_headers = ['Column Name', 'Column Functional Name', 'Comments / Notes']
        instruction_header_format = workbook.add_format({'bold': True})

        for col_idx, header_text in enumerate(instruction_headers):
            worksheet_instructions.write(0, col_idx, header_text, instruction_header_format)

        for row_idx, (field, label, mandatory, help_text) in enumerate(instructions_data):
            display_label = f"{label}*" if mandatory else label
            worksheet_instructions.write(row_idx + 1, 0, field)
            worksheet_instructions.write(row_idx + 1, 1, display_label)
            worksheet_instructions.write(row_idx + 1, 2, help_text)

        for col_idx, header_text in enumerate(instruction_headers):
            max_len = len(header_text)
            for row_data in instructions_data:
                current_len = len(str(row_data[col_idx]))
                if current_len > max_len:
                    max_len = current_len
            worksheet_instructions.set_column(col_idx, col_idx, max_len + 4)

    def _generate_asset_import_template(self, company_id):
        """
        Generates an Excel file with:
        - Sheet 1: Asset import template (headers, example, comments)
        - Sheet 2: Instructions (column details, notes)
        """
        technical_headers = self._get_technical_headers()
        all_example_rows = self._get_localized_example_data(company_id, request.env)
        instructions_data = self._get_instructions_data()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        self._write_asset_sheet(workbook, technical_headers, all_example_rows)
        self._write_instructions_sheet(workbook, instructions_data)

        workbook.close()
        return output.getvalue()
