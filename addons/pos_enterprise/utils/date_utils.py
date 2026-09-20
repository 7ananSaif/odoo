from odoo import fields


def compute_seconds_since(start_time):
    """Compute the number of minutes since the given datetime."""
    return (fields.Datetime.now() - start_time).total_seconds()
