from odoo import api, fields, models

CONTROL_METHODS = [
    ('co_1', "Company - Cat 1. Capital Ownership or voting rights"),
    ('co_2', "Company - Cat 2. Control by other means"),
    ('co_3', "Company - Cat 3. Executive officer"),
    ('ngo_1', "NGO - Cat 1. Directors"),
    ('ngo_2', "NGO - Cat 2. Individuals with representation authority"),
    ('ngo_3', "NGO - Cat 3. Individuals responsible for day-to-day management"),
    ('ngo_4', "NGO - Cat 4. Founders of a foundation"),
    ('ngo_5', "NGO - Cat 5. Individuals or categories of individuals in whose main interest the association or foundation has been established or operates"),
    ('ngo_6', "NGO - Cat 6. Any other individual who ultimately exercises control by other means"),
]

ACTIVATE_PERCENTAGES = ['co_1']  # control methods that allow the user to input percentages
ACTIVATE_ROLE = ['co_3', 'ngo_2']  # control methods that allow the user to input auth rep role

AUTH_REP_ROLES = [
    ('board_member', "Board Member"),
    ('managing_director', "Managing Director"),
    ('chairman', "Chairman of the Board"),
    ('auditor', "Auditor"),
    ('liquidator', "Liquidator"),
    ('ceo', "CEO"),
    ('secretary', "Secretary"),
    ('treasurer', "Treasurer"),
]


class EquityUbo(models.Model):
    _name = 'equity.ubo'
    _inherit = ['mail.thread']
    _description = "Ultimate Beneficial Owner"

    partner_id = fields.Many2one(
        'res.partner',
        string="Company",
        required=True,
        domain=[('is_company', '=', True)],
        index=True,
    )
    holder_id = fields.Many2one(
        'res.partner',
        string="Holder",
        required=True,
        domain=[('is_company', '=', False)],
        index=True,
    )

    start_date = fields.Date(string="Control Start Date", required=True)
    end_date = fields.Date(string="Control End Date")

    control_method = fields.Selection(
        selection=CONTROL_METHODS,
        required=True,
        default='co_1',
    )
    has_percentages = fields.Boolean(compute='_compute_has_percentages')
    ownership = fields.Float()
    voting_rights = fields.Float()
    has_auth_rep_role = fields.Boolean(compute='_compute_has_auth_rep_role')
    auth_rep_role = fields.Selection(selection=AUTH_REP_ROLES, string="Role", help="Authorized Representative Role")

    attachment_expiration_date = fields.Date("Document Exp. Date")
    attachment_ids = fields.One2many(comodel_name='ir.attachment', inverse_name='res_id', string="Attachments")

    _unique_ubo = models.Constraint(
        'unique (partner_id, holder_id)',
        "This contact is already a holder of this company",
    )

    @api.depends('partner_id.name', 'holder_id.name')
    def _compute_display_name(self):
        for ubo in self:
            if ubo.partner_id and ubo.holder_id:
                ubo.display_name = self.env._(
                    "%(partner_name)s (%(holder_name)s)",
                    partner_name=ubo.partner_id.name,
                    holder_name=ubo.holder_id.name,
                )
            else:
                ubo.display_name = ""

    @api.depends('control_method')
    def _compute_has_percentages(self):
        for ubo in self:
            ubo.has_percentages = ubo.control_method in ACTIVATE_PERCENTAGES

    @api.depends('control_method')
    def _compute_has_auth_rep_role(self):
        for ubo in self:
            ubo.has_auth_rep_role = ubo.control_method in ACTIVATE_ROLE

    @api.onchange('control_method', 'ownership', 'voting_rights', 'auth_rep_role')
    def _onchange_control_method(self):
        for ubo in self:
            if not ubo.has_percentages:
                ubo.ownership = 0
                ubo.voting_rights = 0
            if not ubo.has_auth_rep_role:
                ubo.auth_rep_role = False

    @api.model
    def submit_ubo_form_data(self, partner_id, data):
        """
            :param data: list of new or existing (if has an id) equity.ubo dicts with a holder_id sub-record dict.
                Each record may have `attachment` which holds a file that should be uploaded to the record chatter.
        """
        try:
            for data_record in data:
                attachment_data = data_record.pop('attachment', None)
                holder_data = data_record.pop('holder_id')
                if ubo_id := data_record.pop('id', None):
                    ubo = self.browse(ubo_id)
                    ubo.write(data_record)
                    assert holder_data.pop('id') == ubo.holder_id.id
                    ubo.holder_id.write(holder_data)
                else:
                    holder = self.env['res.partner'].create(holder_data)
                    ubo = self.create({
                        'partner_id': partner_id,
                        'holder_id': holder.id,
                        **data_record,
                    })

                if attachment_data:
                    self.env['ir.attachment'].create({
                        'name': attachment_data['name'],
                        'mimetype': attachment_data['type'],
                        'datas': attachment_data['data'],
                        'res_model': self._name,
                        'res_id': ubo.id,
                    })
        except Exception as e:  # noqa: BLE001
            return {'error': self.env._("Invalid data: %s", e)}
