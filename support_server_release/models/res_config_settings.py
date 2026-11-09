# Copyright 2026 Akretion (http://www.akretion.com).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    support_server_release_stage_preprod_id = fields.Many2one(
        "project.task.type",
        string="Preprod stage",
        config_parameter="support_server_release.stage_preprod_id",
        help="Stage applied to the tickets when a release is received from preprod.",
    )
    support_server_release_stage_prod_id = fields.Many2one(
        "project.task.type",
        string="Prod stage",
        config_parameter="support_server_release.stage_prod_id",
        help="Stage applied to the tickets when a release is received from prod.",
    )
