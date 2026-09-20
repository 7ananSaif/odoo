from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_co_dian_operation_mode_ids = fields.One2many(
        string="DIAN Operation Modes",
        related="company_id.l10n_co_dian_operation_mode_ids",
        readonly=False,
        help="Software configurations of DIAN",
    )
    l10n_co_dian_certificate_ids = fields.One2many(
        string="Software Certificates",
        related='company_id.l10n_co_dian_certificate_ids',
        readonly=False,
        help="Certificates to be used for electronic invoicing.",
    )
    l10n_co_dian_test_environment = fields.Boolean(
        string="Test environment",
        related='company_id.l10n_co_dian_test_environment',
        readonly=False,
        help="Activate this checkbox if you’re testing workflows for electronic invoicing.",
    )
    l10n_co_dian_certification_process = fields.Boolean(
        string="Activate the certification process",
        related='company_id.l10n_co_dian_certification_process',
        readonly=False,
        help="Activate this checkbox if you are in the certification process with the DIAN.",
    )
    l10n_co_dian_provider = fields.Selection(
        string="Electronic Invoicing Provider",
        related='company_id.l10n_co_dian_provider',
        readonly=False,
        required=True,
    )
    l10n_co_dian_demo_mode = fields.Boolean(
        string="DIAN Demo Mode",
        related='company_id.l10n_co_dian_demo_mode',
        readonly=False,
        help="Activate this checkbox if you’re testing elecronic invoice flows with internal validation.",
    )
    l10n_co_dian_cert_invoice_count = fields.Integer(
        string="Number of Invoices to Certify",
        default=5,
    )
    l10n_co_dian_cert_credit_count = fields.Integer(
        string="Number of Credit Notes to Certify",
        default=5,
    )
    l10n_co_dian_cert_debit_count = fields.Integer(
        string="Number of Debit Notes to Certify",
        default=5,
    )

    @api.constrains('l10n_co_dian_cert_invoice_count', 'l10n_co_dian_cert_credit_count', 'l10n_co_dian_cert_debit_count')
    def _check_l10n_co_dian_cert_fields(self):
        for setting in self:
            invoice_count = setting.l10n_co_dian_cert_invoice_count
            debit_count = setting.l10n_co_dian_cert_debit_count
            credit_count = setting.l10n_co_dian_cert_credit_count
            if not all(0 <= count < 10 for count in [invoice_count, debit_count, credit_count]):
                raise ValidationError(self.env._("The number of invoices, credit notes, or debit notes to certify must be between 0 and 10."))

    # ----------------------------------------------------------------
    # Certification Methods
    # Users are expected to go through a certification process for the
    # DIAN to allow their integration. For users just coming to Odoo
    # this can be a confusing process. As such these methods automate
    # the process and are expected to be used in a staging or testing
    # database.
    # ----------------------------------------------------------------

    def action_l10n_co_certify_with_dian(self):
        """ Automates the required certification flow that's needed to use this
        module in production. It's hard and confusing for new users. Only
        expected to be called in a testing or staging database as it makes
        irreversible changes. """
        if not self.l10n_co_dian_test_environment or not self.l10n_co_dian_certification_process:
            raise ValidationError(self.env._("This action must only be called while in certification mode."))

        journal_ids = self._l10n_co_dian_certify_create_or_update_journals()
        product_id = self._l10n_co_dian_certify_create_or_update_product()
        invoice_journal = journal_ids.filtered(lambda j: j.code == 'SETP')
        credit_journal = journal_ids.filtered(lambda j: j.code == 'NC')
        debit_journal = journal_ids.filtered(lambda j: j.code == 'ND')

        all_moves = self._l10n_co_dian_certify_create_moves(
            invoice_journal,
            product_id,
            self.l10n_co_dian_cert_invoice_count,
            move_type='out_invoice',
            l10n_co_edi_type='01',
            l10n_co_edi_operation_type='10',
        )

        all_moves |= self._l10n_co_dian_certify_create_moves(
                credit_journal,
                product_id,
                self.l10n_co_dian_cert_credit_count,
                move_type='out_refund',
                l10n_co_edi_type='91',
                l10n_co_edi_operation_type='22',
                l10n_co_edi_description_code_credit='1',
        )

        all_moves |= self._l10n_co_dian_certify_create_moves(
                debit_journal,
                product_id,
                self.l10n_co_dian_cert_debit_count,
                move_type='out_invoice',
                l10n_co_edi_type='92',
                l10n_co_edi_operation_type='32',
                l10n_co_edi_description_code_debit='1',
        )

        for move in all_moves:
            move.l10n_co_dian_action_send_bill_support_document()

        for move in all_moves:
            move.l10n_co_dian_document_ids.action_get_status()

        self.env.user._bus_send('account_notification', {
            'type': 'info',
            'title': self.env._('Certification Process Has Concluded'),
            'sticky': True,
            'message': self.env._('Please click below to check the status of your documents.'),
            'action_button': {
                'name': self.env._('Open'),
                'action_name': self.env._('All Documents'),
                'model': 'account.move',
                'res_ids': all_moves.ids,
            },
        })

    def _l10n_co_dian_certify_create_or_update_journals(self):
        default_account = self.env['account.chart.template'].ref('co_puc_417500')
        all_journals = self.env['account.journal']

        journal_info = [
            {
                'code': 'SETP',
                'name': 'DIAN Facturas de Cliente',
                'is_debit_note': False,
                'min_range_number': 990000000,
                'max_range_number': 995000000,
            },
            {
                'code': 'NC',
                'name': 'DIAN Notas Credito',
                'is_debit_note': False,
                'min_range_number': 1,
                'max_range_number': 1000,
            },
            {
                'code': 'ND',
                'name': 'DIAN Notas Debito',
                'is_debit_note': True,
                'min_range_number': 1,
                'max_range_number': 1000,
            },
        ]
        for journal_data in journal_info:
            journal = self.env['account.journal'].search([('code', '=', journal_data['code'])])
            if not journal:
                journal = self.env['account.journal'].create({
                    'name': journal_data['name'],
                    'type': 'sale',
                    'code': journal_data['code'],
                    'company_id': self.company_id.id,
                    'l10n_co_edi_debit_note': journal_data['is_debit_note'],
                })
            journal.write({
                'l10n_co_edi_min_range_number': journal_data['min_range_number'],
                'l10n_co_edi_max_range_number': journal_data['max_range_number'],
            })
            all_journals |= journal

        # The DIAN requires that all customers performing the certification process always
        # use this Technical Key and authorization number. As such it can be hardcoded in
        # the action.
        all_journals.write({
            'l10n_co_dian_technical_key': 'fc8eac422eba16e22ffd8c6f94b3f40a6e38162c',
            'l10n_co_edi_dian_authorization_date': '2019-01-19',
            'l10n_co_edi_dian_authorization_end_date': '2030-01-19',
            'l10n_co_edi_dian_authorization_number': '18760000001',
            'default_account_id': default_account.id,
        })

        return all_journals

    def _l10n_co_dian_certify_create_or_update_product(self):
        default_sales_tax = self.env['account.chart.template'].ref('l10n_co_tax_8')
        default_purchase_tax = self.env['account.chart.template'].ref('l10n_co_tax_1')
        product_id = self.env['product.product'].search([('default_code', '=', 'PC1')])
        if not product_id:
            product_id = self.env['product.product'].create({
                'name': 'Producto Certificación',
                'default_code': 'PC1',
                'type': 'consu',
                'categ_id': self.env.ref('product.product_category_goods').id,
                'company_id': self.company_id.id,
            })
        product_id.write({
            'list_price': 1000000.0,
            'taxes_id': [(6, 0, default_sales_tax.ids)],
            'supplier_taxes_id': [(6, 0, default_purchase_tax.ids)],
            'sale_ok': True,
            'purchase_ok': True,
        })

        return product_id

    def _l10n_co_dian_certify_create_moves(self, journal_id, product_id, count, **move_values):
        all_moves = self.env['account.move']
        if count == 0:
            return all_moves

        move = self.env['account.move'].create({
            'partner_id': self.env.ref('l10n_co_edi.consumidor_final_customer').id,
            'journal_id': journal_id.id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_date_due': fields.Date.context_today(self),
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': product_id.id,
                    'quantity': 1.0,
                }),
            ],
           **move_values,
        })

        # Start the sequence with the min number if there isn't already one.
        if not move._get_last_sequence():
            move.name = f"{journal_id.code}{journal_id.l10n_co_edi_min_range_number}"

        move.action_post()

        all_moves |= move
        for _ in range(count - 1):
            new_move = move.copy()
            new_move.action_post()
            all_moves |= new_move
        return all_moves
