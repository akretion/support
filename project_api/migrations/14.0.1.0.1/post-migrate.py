from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["project.project"].search([("partner_id", "!=", False)]).write({"customer_display": True})
