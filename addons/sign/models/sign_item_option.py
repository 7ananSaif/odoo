# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SignItemOption(models.Model):
    _name = 'sign.item.option'
    _description = "Option of a selection Field"
    _rec_name = "value"

    value = fields.Text(string="Option", readonly=True)

    _value_uniq = models.Constraint(
        'unique (value)',
        "Value already exists!",
    )

    def get_selection_ids_from_value(self, options):
        """This method takes a list of text options, checks which options
        already exist in the database, creates the missing ones, and
        returns a list of IDs corresponding to all provided options
        (both existing and newly created).
        """
        options = list(set(options))
        existing_values = {opt['value'] for opt in self.search_read([('value', 'in', options)], fields=['value'])}
        new_options = [option for option in options if option not in existing_values]
        if new_options:
            self.create([{'value': option} for option in new_options])
        return self.search([('value', 'in', options)]).ids
