from odoo.addons.account_reports.tests.common import TestAccountReportsCommon

from odoo import Command
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nCoReportsWithholding(TestAccountReportsCommon):
    @classmethod
    @TestAccountReportsCommon.setup_country('co')
    def setUpClass(cls):
        super().setUpClass()

        cls.report_ica = cls.env.ref('l10n_co_reports.l10n_co_reports_ica')
        cls.report_iva = cls.env.ref('l10n_co_reports.l10n_co_reports_iva')
        cls.report_fuente = cls.env.ref('l10n_co_reports.l10n_co_reports_fuente')

    def _l10n_co_create_moves_with_taxes(self, taxes):
        """
        Create three generic moves with different partners, dates and taxes applied to test various report elements in a uniform manner.
        """
        move_1 = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2025-01-01',
            'invoice_line_ids': [Command.create({
                'product_id': self.product_a.id,
                'quantity': 1.0,
                'name': 'product test 1',
                'price_unit': 100,
                'tax_ids': taxes[0].ids,
            }), Command.create({
                'product_id': self.product_b.id,
                'quantity': 1.0,
                'name': 'product test 2',
                'price_unit': 100,
                'tax_ids': taxes[1].ids,
            })]
        })
        move_2 = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2024-11-02',
            'invoice_line_ids': [Command.create({
                'product_id': self.product_a.id,
                'quantity': 10.0,
                'name': 'product test 1',
                'price_unit': 100,
                'tax_ids': taxes[2].ids,
            })]
        })
        move_3 = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_b.id,
            'invoice_date': '2025-01-02',
            'invoice_line_ids': [Command.create({
                'product_id': self.product_a.id,
                'quantity': 3.0,
                'name': 'product test 1',
                'price_unit': 100,
                'tax_ids': taxes[3].ids,
            }), Command.create({
                'product_id': self.product_b.id,
                'quantity': 3.0,
                'name': 'product test 2',
                'price_unit': 100,
                'tax_ids': taxes[4].ids,
            })]
        })
        (move_1 + move_2 + move_3).action_post()

    def test_co_withholding_ica(self):
        """
            Ensure that an ICA report is generated as expected
        """
        tax_ica_1 = self.env['account.chart.template'].ref('l10n_co_tax_44')
        tax_ica_2 = self.env['account.chart.template'].ref('l10n_co_tax_45')
        tax_ica_3 = self.env['account.chart.template'].ref('l10n_co_tax_46')
        self._l10n_co_create_moves_with_taxes([tax_ica_1, tax_ica_2, tax_ica_3, tax_ica_1, tax_ica_2])
        options = self._generate_options(
            self.report_ica, '2024-11-01', '2025-02-03',
        )
        lines = self.report_ica._get_lines(options)
        self.assertLinesValues(
            # pylint: disable=bad-whitespace
            lines,
            #     Partner ID,                bimestre,    base,     tax,       ICA type
            [              0,                       1,       2,       3,              4],
            [
                ('partner_a',                      '', 1200.00,    5.93,             ''),
                ('partner_b',                      '',  600.00,    5.38,             ''),
            ],
            options,
        )
        expanded_line = self.report_ica.get_expanded_lines(
            options, lines[0]['id'], self.partner_a, lines[0]['expand_function'], 0, 0, None,
        )
        self.assertLinesValues(
            # pylint: disable=bad-whitespace
            expanded_line,
            #     Partner ID,                bimestre,    base,     tax,       ICA type
            [              0,                       1,       2,       3,              4],
            [
                (         '',       'Enero - Febrero',  100.00,    0.69, tax_ica_1.name),
                (         '',       'Enero - Febrero',  100.00,    1.10, tax_ica_2.name),
                (         '', 'Noviembre - Diciembre', 1000.00,    4.14, tax_ica_3.name),
            ],
            options,
        )

    def test_co_withholding_iva(self):
        """
            Ensure that an IVA report is generated as expected
        """
        tax_iva_1 = self.env['account.chart.template'].ref('l10n_co_tax_12')
        tax_iva_2 = self.env['account.chart.template'].ref('l10n_co_tax_13')
        self._l10n_co_create_moves_with_taxes([tax_iva_1, tax_iva_2, tax_iva_1, tax_iva_2, tax_iva_1])
        options = self._generate_options(
            self.report_iva, '2024-11-01', '2025-02-03',
        )
        lines = self.report_iva._get_lines(options)
        self.assertLinesValues(
            # pylint: disable=bad-whitespace
            lines,
            #     Partner ID,               bimestre, retention,     tax,    base, RteIVA %
            [              0,                      1,         2,       3,       4,        5],
            [
                ('partner_a',                     '',     32.10,  214.00, 1200.00,  '15.0%'),
                ('partner_b',                     '',     10.80,    72.0,  600.00,  '15.0%'),
            ],
            options,
        )
        expanded_line = self.report_iva.get_expanded_lines(
            options, lines[0]['id'], self.partner_a, lines[0]['expand_function'], 0, 0, None,
        )
        self.assertLinesValues(
            # pylint: disable=bad-whitespace
            expanded_line,
            #     Partner ID,               bimestre, retention,     tax,    base, RteIVA %
            [              0,                      1,         2,       3,       4,        5],
            [
                (         '',       'Enero - Febrero',     3.60,   24.00,  200.00,  '15.0%'),
                (         '', 'Noviembre - Diciembre',    28.50,  190.00, 1000.00,  '15.0%'),
            ],
            options,
        )

    def test_co_withholding_fuente(self):
        """
            Ensure that a Fuente report is generated as expected
        """
        tax_fuente_1 = self.env['account.chart.template'].ref('l10n_co_tax_16')
        tax_fuente_2 = self.env['account.chart.template'].ref('l10n_co_tax_17')
        tax_fuente_3 = self.env['account.chart.template'].ref('l10n_co_tax_18')
        self._l10n_co_create_moves_with_taxes([tax_fuente_1, tax_fuente_2, tax_fuente_3, tax_fuente_1, tax_fuente_2])
        options = self._generate_options(
            self.report_fuente, '2024-11-01', '2025-02-03',
        )
        lines = self.report_fuente._get_lines(options)
        self.assertLinesValues(
            # pylint: disable=bad-whitespace
            lines,
            #     Partner ID,                                 type,    base,     tax
            [              0,                                    1,       2,       3],
            [
                ('partner_a',                                   '', 1200.00,  100.60),
                ('partner_b',                                   '',  600.00,    1.80),
            ],
            options,
        )
        expanded_line = self.report_fuente.get_expanded_lines(
            options, lines[0]['id'], self.partner_a, lines[0]['expand_function'], 0, 0, None,
        )
        self.assertLinesValues(
            # pylint: disable=bad-whitespace
            expanded_line,
            #     Partner ID,                                 type,    base,     tax
            [              0,                                    1,       2,       3],
            [
                (         '', tax_fuente_1.description.striptags(),  100.00,    0.10),
                (         '', tax_fuente_2.description.striptags(),  100.00,    0.50),
                (         '', tax_fuente_3.description.striptags(), 1000.00,  100.00),
            ],
            options,
        )
