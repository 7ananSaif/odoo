from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class L10n_AuHrInputDetails(models.Model):
    _name = "l10n_au.hr.input.details"
    _description = "Other Input Details"

    input_id = fields.Many2one(
        comodel_name="hr.payslip.input",
        string="Input Name",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    input_type_id = fields.Many2one(related="input_id.input_type_id", string="Input Type")
    name = fields.Char(
        string="Description",
        compute="_compute_name"
    )
    payslip_id = fields.Many2one(related="input_id.payslip_id", string="Payslip", store=True)

    # For Inputs that require the number of days or distance
    code = fields.Char(related="input_id.code", string="Code")
    input_uom = fields.Selection(depends=["input_id.input_type_id"], related="input_id.input_type_id.l10n_au_input_uom")
    quantity = fields.Float(string="Quantity", inverse="_update_amount")

    # For backpayments
    is_backpayment = fields.Boolean(string="Is Backpayment", compute="_compute_is_backpayment")
    date = fields.Date(string="Backpay Date")

    # For Travel Allowances
    city_id = fields.Many2one(comodel_name="res.city", string="City", domain="[('country_id.code', '=', 'AU')]",
        help="City for Domestic Travel Allowances")
    country_id = fields.Many2one(
        comodel_name="res.country", string="Country", help="Country for Overseas Travel Allowances",
    )
    # CPK Allowance
    rate = fields.Float(
        string="Rate",
        help="Rate for the Cents per Kilometer allowances",
        inverse="_update_amount",
        compute="_compute_rate",
        store=True
    )

    @api.ondelete(at_uninstall=False)
    def _prevent_delete(self):
        """Prevent deletion if the input line is not deleted"""
        if self.input_id.input_type_id.l10n_au_requires_details and self.input_id.l10n_au_treatment == "backpay":
            raise ValidationError(_("You cannot delete input details that are linked to an existing payslip input."))

    @api.depends("input_id.input_type_id", "input_id.name")
    def _compute_name(self):
        for record in self:
            record.name = f"{record.input_id.name} ({record.input_id.input_type_id.name})" if record.input_id.name else record.input_id.input_type_id.name

    @api.depends("input_id.l10n_au_treatment")
    def _compute_is_backpayment(self):
        """Compute if the input is a backpayment based on the payslip date."""
        for record in self:
            record.is_backpayment = record.input_id.l10n_au_treatment == "backpay"

    @api.depends("input_id.input_type_id", "input_id.amount")
    def _compute_rate(self):
        for record in self:
            if record.code != "ALW.CPK":
                record.rate = False
            else:
                if record.input_id.amount and record.quantity:
                    record.rate = record.input_id.amount / record.quantity
                else:
                    record.rate = record.payslip_id._rule_parameter("l10n_au_allowance_cpk")["claimable"]

    def _update_amount(self):
        """ Update the amount of the input based on the quantity and rate."""
        for record in self.filtered(lambda r: r.code == "ALW.CPK"):
            record.input_id.amount = record.quantity * record.rate

    @api.onchange("input_uom", "quantity")
    def _onchange_input_uom(self):
        if self.input_uom == "days":
            self.quantity = round(self.quantity, 0)

    def _check_input_details(self):
        for record in self:
            if record.code == "ALW.CPK":
                if record.quantity < 0:
                    raise ValidationError(_("Cents Per Kilometre Allowances require the Number of kilometres on the input details."))
                min_claimable_rate = record.payslip_id._rule_parameter("l10n_au_allowance_cpk")["claimable"]
                if record.rate < min_claimable_rate:
                    raise ValidationError(_(
                        "Cents Per Kilometre Allowance amount must be greater than or equal to the minimum rate of %.2f for the current pay period.",
                        min_claimable_rate
                    ))
            elif record.code == "ALW.DTA" and not (record.city_id and record.quantity):
                raise ValidationError(_("Domestic Travel Allowance requires a City and Number of days to be set."))
            elif record.code == "ALW.OTA":
                if record.country_id.code != "AU" or not record.quantity:
                    raise ValidationError(_("Overseas Travel Allowance requires an overseas Country and Number of days to be set."))
                country_group = record.payslip_id._rule_parameter("l10n_au_country_groups").get(record.country_id.code, False)
                if not country_group:
                    raise ValidationError(_("%s is not a valid country for Overseas Travel Allowance.", record.country_id.name))
