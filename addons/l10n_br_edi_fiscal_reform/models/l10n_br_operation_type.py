# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class L10n_BrOperationType(models.Model):
    _inherit = 'l10n_br.operation.type'

    # TODO JOV: add to view
    has_inbound_cbs_ibs_credit = fields.Boolean(
        'CBS/IBS Credit',
        help='Brazil: Indicates if CBS/IBS tax paid on inbound operations can be claimed as a tax credit.'
    )
    is_used_movable_good = fields.Boolean(
        'Used Goods from Non-Taxpayer / MEI',
        help='Brazil: Enable this option if the supply involves used movable goods purchased from an individual who is '
             'either not a taxpayer or registered as an MEI (Individual Microentrepreneur).'
    )
    credit_classification = fields.Selection(
        [
            ('0', 'No Presumed Credit'),
            ('1', 'Final consumer goods (55%)'),
            ('2', 'Capital goods (75%)'),
            ('3', 'Intermediate goods (90.25%)'),
            ('4', 'Computer goods and others defined in legislation (100%)'),
        ],
        string='Presumed Credit Classification (ZFM)',
        help='Brazil: Classification according to the percentages defined in art. 450, §1, of LC 214/25 for the '
            'calculation of the presumed credit. Only used for transactions with the Manaus Free Trade Zone (ZFM)'
    )
    is_donation = fields.Boolean(
        'Is Donation',
        help='Brazil: Indicates whether this transaction line refers to a donation. If enabled, the NF-e will be '
             'generated with indDoacao = 1.'
    )
    l10n_br_customs_regime_id = fields.Many2one(
        'l10n_br.customs.regime',
        string='Special Customs Regime',
        help='Brazil: Optional value to be selected if the transaction for the capital good is subject to a special customs regime.',
    )
    # These technical values are hardcoded on Avalara's side, and shouldn't change, so we'll do a Selection field.
    l10n_br_transaction_usage = fields.Selection(
        [
            ("Táxi", "Taxi"),
            ("Pessoas com Deficiência", "People with Disabilities"),
            ("Projetos de reabilitação urbana", "Urban Rehabilitation Projects"),
            ("Industrialização por encomenda", "Manufacturing by Order"),
            ("Locação dos imóveis localizados nas zonas reabilitadas", "Lease of Properties Located in Rehabilitated Zones"),
            ("Ferrovia", "Railway"),
            ("Depende de Evento Posterior", "Subject to a Subsequent Event"),
            ("Ativo financeiro ou instrumento cambial", "Financial Asset or Foreign Exchange Instrument"),
            ("Exploração de via", "Roadway Operation"),
            ("Contribuição de Melhoria", "Improvement Contribution"),
            ("Operações não onerosas sem previsão de IBS/CBS", "Non-Onerous Transactions without IBS/CBS Applicability"),
            ("Gorjeta até 15%", "Tip up to 15%"),
            ("Livre e Gratuita", "Free of Charge"),
            ("Operação Equiparada à Exportação", "Transaction Equivalent to Export"),
            ("Exportação Indireta", "Indirect Export"),
            ("Plataforma digital de entrega", "Digital Delivery Platform"),
            ("Matéria-prima", "Raw Material"),
            ("Embalagem", "Packaging"),
            ("Ativo Imobilizado", "Fixed Asset"),
            ("Produto Intermediário", "Intermediate Product"),
        ],
        help="Brazil: Defines the fiscal classification of how the good or service is used in the transaction, which may impact tax calculation and invoice request."
    )
    l10n_br_service_operation_indicator = fields.Char(
        'Service Operation Indicator',
        help="Brazil: Defines the specific “indOp” operation indicator code for the service (e.g., '050101'). This value is sent to Avalara for tax calculation and invoice "
             "generation. If left empty, Avalara's automatic calculation may be used, but specific municipal validations may require a manual definition."
    )
