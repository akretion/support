# Copyright 2026 Akretion (http://www.akretion.com).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    use_release_note = fields.Boolean(
        string="Release notes",
        help="Add a release note on the tickets, written by the internal users, "
        "shown to the customer and added to the production mail.",
    )
