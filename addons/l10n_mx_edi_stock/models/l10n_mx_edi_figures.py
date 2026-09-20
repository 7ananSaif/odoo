from odoo import models, fields


class L10nMxEdiFigure(models.Model):
    _name = 'l10n_mx_edi.figure'
    _description = 'MX EDI Vehicle Intermediary Figure'

    vehicle_id = fields.Many2one('fleet.vehicle')
    type = fields.Selection(
        selection=[
            ('01', 'Operador'),
            ('02', 'Propietario'),
            ('03', 'Arrendador'),
            ('04', 'Notificado'),
            ('05', 'Integrante de Coordinados'),
        ])
    operator_id = fields.Many2one(
        comodel_name='res.partner',
        string='Partner',
        help="Register the contact that is involved depending on its responsibility in the transport (Operador, "
             "Propietario, Arrendador, Notificado)")
    part_ids = fields.Many2many('l10n_mx_edi.part', string='Parts')


class L10nMxEdiPart(models.Model):
    _name = 'l10n_mx_edi.part'
    _description = 'MX EDI Intermediary Part'

    code = fields.Char(required=True)
    name = fields.Char(required=True)
