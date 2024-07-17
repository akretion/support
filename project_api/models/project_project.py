# Copyright 2018 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, tools


class ProjectProject(models.Model):
    _inherit = "project.project"

    customer_project_name = fields.Char(
        help="Name that will appear on customer support menu", index=True
    )
    subscribe_assigned_only = fields.Boolean(
        string="Subscribe assigned only",
        help="When a user get assigned, unscubscribe automaticaly other users",
    )
    customer_display = fields.Boolean(
        index=True,
        help="The tasks of this project will be displayed on customer side only if this"
             " box is checked")

    def _get_customer_project_name(self):
        return self.customer_project_name or self.name
