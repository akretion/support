# Copyright 2026 Akretion (http://www.akretion.com).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    support_release_notification_user_ids = fields.Many2many(
        "res.users",
        "support_release_notification_user_rel",
        "partner_id",
        "user_id",
        string="Release notification users",
        help="Users notified by mail when a release of this customer "
        "reaches production.",
    )
