# Copyright 2026 Akretion (http://www.akretion.com).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    release_ids = fields.Many2many(
        "support.server.release",
        relation="support_server_release_project_task_rel",
        column1="task_id",
        column2="release_id",
        string="Releases",
    )

    def action_open_releases(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Releases"),
            "res_model": "support.server.release",
            "view_mode": "list,form",
            "domain": [("id", "in", self.release_ids.ids)],
        }
