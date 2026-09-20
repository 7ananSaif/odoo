from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    l10n_mx_transport_perm_number = fields.Char(
        string='SCT Permit Number',
        help='The permit number granted to the unit performing the transfer of goods')
    l10n_mx_transport_insurer = fields.Char('Insurance Company', help='The name of the insurer that covers the liability risks of the vehicle')
    l10n_mx_transport_insurance_policy = fields.Char('Insurance Policy Number')
    l10n_mx_transport_perm_sct = fields.Selection(
        selection=[
            ('TPAF01', 'Autotransporte Federal de carga general.'),
            ('TPAF02', 'Transporte privado de carga.'),
            ('TPAF03', 'Autotransporte Federal de Carga Especializada de materiales y residuos peligrosos.'),
            ('TPAF04', 'Transporte de automóviles sin rodar en vehículo tipo góndola.'),
            ('TPAF05', 'Transporte de carga de gran peso y/o volumen de hasta 90 toneladas.'),
            ('TPAF06', 'Transporte de carga especializada de gran peso y/o volumen de más 90 toneladas.'),
            ('TPAF07', 'Transporte Privado de materiales y residuos peligrosos.'),
            ('TPAF08', 'Autotransporte internacional de carga de largo recorrido.'),
            ('TPAF09', 'Autotransporte internacional de carga especializada de materiales y residuos peligrosos de largo recorrido.'),
            ('TPAF10', 'Autotransporte Federal de Carga General cuyo ámbito de aplicación comprende la franja fronteriza con Estados Unidos.'),
            ('TPAF11', 'Autotransporte Federal de Carga Especializada cuyo ámbito de aplicación comprende la franja fronteriza con Estados Unidos.'),
            ('TPAF12', 'Servicio auxiliar de arrastre en las vías generales de comunicación.'),
            ('TPAF13', 'Servicio auxiliar de servicios de arrastre, arrastre y salvamento, y depósito de vehículos en las vías generales de comunicación.'),
            ('TPAF14', 'Servicio de paquetería y mensajería en las vías generales de comunicación.'),
            ('TPAF15', 'Transporte especial para el tránsito de grúas industriales con peso máximo de 90 toneladas.'),
            ('TPAF16', 'Servicio federal para empresas arrendadoras servicio público federal.'),
            ('TPAF17', 'Empresas trasladistas de vehículos nuevos.'),
            ('TPAF18', 'Empresas fabricantes o distribuidoras de vehículos nuevos.'),
            ('TPAF19', 'Autorización expresa para circular en los caminos y puentes de jurisdicción federal con configuraciones de tractocamión doblemente articulado.'),
            ('TPAF20', 'Autotransporte Federal de Carga Especializada de fondos y valores.'),
            ('TPTM01', 'Permiso temporal para navegación de cabotaje'),
            ('TPTA01', 'Concesión y/o autorización para el servicio regular nacional y/o internacional para empresas mexicanas'),
            ('TPTA02', 'Permiso para el servicio aéreo regular de empresas extranjeras'),
            ('TPTA03', 'Permiso para el servicio nacional e internacional no regular de fletamento'),
            ('TPTA04', 'Permiso para el servicio nacional e internacional no regular de taxi aéreo'),
            ('TPXX00', 'Permiso no contemplado en el catálogo.')
        ],
        string='SCT Permit Type',
        help='The type of permit code to carry out the goods transfer service')
    l10n_mx_vehicle_config = fields.Selection(
        selection=[
            ('VL', 'Vehículo ligero de carga (2 llantas en el eje delantero y 2 llantas en el eje trasero)'),
            ('C2', 'Camión Unitario (2 llantas en el eje delantero y 4 llantas en el eje trasero)'),
            ('C3', 'Camión Unitario (2 llantas en el eje delantero y 6 o 8 llantas en los dos ejes traseros)'),
            ('C2R2', 'Camión-Remolque (6 llantas en el camión y 8 llantas en remolque)'),
            ('C3R2', 'Camión-Remolque (10 llantas en el camión y 8 llantas en remolque)'),
            ('C2R3', 'Camión-Remolque (6 llantas en el camión y 12 llantas en remolque)'),
            ('C3R3', 'Camión-Remolque (10 llantas en el camión y 12 llantas en remolque)'),
            ('T2S1', 'Tractocamión Articulado (6 llantas en el tractocamión, 4 llantas en el semirremolque)'),
            ('T2S2', 'Tractocamión Articulado (6 llantas en el tractocamión, 8 llantas en el semirremolque)'),
            ('T2S3', 'Tractocamión Articulado (6 llantas en el tractocamión, 12 llantas en el semirremolque)'),
            ('T3S1', 'Tractocamión Articulado (10 llantas en el tractocamión, 4 llantas en el semirremolque)'),
            ('T3S2', 'Tractocamión Articulado (10 llantas en el tractocamión, 8 llantas en el semirremolque)'),
            ('T3S3', 'Tractocamión Articulado (10 llantas en el tractocamión, 12 llantas en el semirremolque)'),
            ('T2S1R2', 'Tractocamión Semirremolque-Remolque (6 llantas en el tractocamión, 4 llantas en el semirremolque y 8 llantas en el remolque)'),
            ('T2S2R2', 'Tractocamión Semirremolque-Remolque (6 llantas en el tractocamión, 8 llantas en el semirremolque y 8 llantas en el remolque)'),
            ('T2S1R3', 'Tractocamión Semirremolque-Remolque (6 llantas en el tractocamión, 4 llantas en el semirremolque y 12 llantas en el remolque)'),
            ('T3S1R2', 'Tractocamión Semirremolque-Remolque (10 llantas en el tractocamión, 4 llantas en el semirremolque y 8 llantas en el remolque)'),
            ('T3S1R3', 'Tractocamión Semirremolque-Remolque (10 llantas en el tractocamión, 4 llantas en el semirremolque y 12 llantas en el remolque)'),
            ('T3S2R2', 'Tractocamión Semirremolque-Remolque (10 llantas en el tractocamión, 8 llantas en el semirremolque y 8 llantas en el remolque)'),
            ('T3S2R3', 'Tractocamión Semirremolque-Remolque (10 llantas en el tractocamión, 8 llantas en el semirremolque y 12 llantas en el remolque)'),
            ('T3S2R4', 'Tractocamión Semirremolque-Remolque (10 llantas en el tractocamión, 8 llantas en el semirremolque y 16 llantas en el remolque)'),
            ('T2S2S2', 'Tractocamión Semirremolque-Semirremolque (6 llantas en el tractocamión, 8 llantas en el semirremolque delantero y 8 llantas en el semirremolque trasero)'),
            ('T3S2S2', 'Tractocamión Semirremolque-Semirremolque (10 llantas en el tractocamión, 8 llantas en el semirremolque delantero y 8 llantas en el semirremolque trasero)'),
            ('T3S3S2', 'Tractocamión Semirremolque-Semirremolque (10 llantas en el tractocamión, 12 llantas en el semirremolque delantero y 8 llantas en el semirremolque trasero)'),
            ('OTROEVGP', 'Especializado de carga Voluminosa y/o Gran Peso'),
            ('OTROSG', 'Servicio de Grúas'),
            ('GPLUTA', 'Grúa de Pluma Tipo A'),
            ('GPLUTB', 'Grúa de Pluma Tipo B'),
            ('GPLUTC', 'Grúa de Pluma Tipo C'),
            ('GPLUTD', 'Grúa de Pluma Tipo D'),
            ('GPLATA', 'Grúa de Plataforma Tipo A'),
            ('GPLATB', 'Grúa de Plataforma Tipo B'),
            ('GPLATC', 'Grúa de Plataforma Tipo C'),
            ('GPLATD', 'Grúa de Plataforma Tipo D'),
        ],
        string='Vehicle Configuration',
        help='The type of vehicle used')
    l10n_mx_gross_vehicle_weight = fields.Float(
        string="Gross Vehicle Weight",
        help="""The vehicle weight, in the case of cargo vehicles; or the sum of the vehicle weight and the weight of the passengers, luggage, and parcels, "
        in the case of vehicles intended for passenger service according to NOM-SCT-012-2017 or its replacement, which, for the purposes of filling out the Carta Porte complement, is expressed in tons. The freight weight will be added on the delivery form.""",
    )
    l10n_mx_trailer_ids = fields.One2many(
        comodel_name='l10n_mx_edi.trailer',
        inverse_name='vehicle_id',
        string='Trailers',
        help='Up to 2 trailers used on this vehicle')
    l10n_mx_figure_ids = fields.One2many(
        comodel_name='l10n_mx_edi.figure',
        inverse_name='vehicle_id',
        string='Intermediaries',
        help='Information corresponding to the transport intermediaries, as well as those taxpayers related to the transportation method used to transport the goods')
    l10n_mx_environment_insurer = fields.Char(
        string="Environment Insurer",
        help="The name of the insurer that covers the liability risks of the environment when transporting hazardous materials")
    l10n_mx_environment_insurance_policy = fields.Char(
        string="Environment Insurance Policy",
        help="Environment Insurance Policy Number - used when transporting hazardous materials")
    l10n_mx_is_freight_vehicle = fields.Boolean()

    @api.constrains('l10n_mx_trailer_ids')
    def _check_trailers(self):
        for vehicle in self:
            if len(vehicle.l10n_mx_trailer_ids) > 2:
                raise ValidationError(_("A maximum of 2 trailers are allowed per vehicle"))
