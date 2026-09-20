from odoo import models, fields


class L10nMxEdiTrailer(models.Model):
    _name = 'l10n_mx_edi.trailer'
    _description = 'MX EDI Vehicle Trailer'

    vehicle_id = fields.Many2one('fleet.vehicle')
    name = fields.Char('Number Plate')
    sub_type = fields.Selection(
        selection=[
            ('CTR001', 'Caballete'),
            ('CTR002', 'Caja'),
            ('CTR003', 'Caja Abierta'),
            ('CTR004', 'Caja Cerrada'),
            ('CTR005', 'Caja De Recolección Con Cargador Frontal'),
            ('CTR006', 'Caja Refrigerada'),
            ('CTR007', 'Caja Seca'),
            ('CTR008', 'Caja Transferencia'),
            ('CTR009', 'Cama Baja o Cuello Ganso'),
            ('CTR010', 'Chasis Portacontenedor'),
            ('CTR011', 'Convencional De Chasis'),
            ('CTR012', 'Equipo Especial'),
            ('CTR013', 'Estacas'),
            ('CTR014', 'Góndola Madrina'),
            ('CTR015', 'Grúa Industrial'),
            ('CTR016', 'Grúa '),
            ('CTR017', 'Integral'),
            ('CTR018', 'Jaula'),
            ('CTR019', 'Media Redila'),
            ('CTR020', 'Pallet o Celdillas'),
            ('CTR021', 'Plataforma'),
            ('CTR022', 'Plataforma Con Grúa'),
            ('CTR023', 'Plataforma Encortinada'),
            ('CTR024', 'Redilas'),
            ('CTR025', 'Refrigerador'),
            ('CTR026', 'Revolvedora'),
            ('CTR027', 'Semicaja'),
            ('CTR028', 'Tanque'),
            ('CTR029', 'Tolva'),
            ('CTR031', 'Volteo'),
            ('CTR032', 'Volteo Desmontable'),
        ],
        string='Sub Type')
