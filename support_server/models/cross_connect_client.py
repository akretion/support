# Copyright 2025 Akretion (http://www.akretion.com).
# @author Florian Mounier <florian.mounier@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from urllib.parse import urlencode

from odoo import models


class CrossConnectClient(models.Model):
    _inherit = "cross.connect.client"

    def _get_final_redirect_url(self, **params):
        """Redirect to project_customer_access with set form default values."""
        url = super()._get_final_redirect_url(**params)
        redirect_params = {}
        if params.get("bypass"):
            redirect_params["action"] = "project.action_view_task"
        else:
            redirect_params["action"] = "project_customer_access.action_view_all_task"

        if params.get("intent") == "new":
            redirect_params.update(
                {
                    "view_type": "form",
                    **{
                        f"project.task_default_{field}": params.get(field)
                        for field in ("origin_db", "origin_name", "origin_url")
                    },
                }
            )

        return f"{url}#{urlencode(redirect_params)}"
