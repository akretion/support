# Copyright 2025 Akretion (http://www.akretion.com).
# @author Florian Mounier <florian.mounier@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import re
from urllib.parse import urlencode, urlparse

from odoo import api, models

AKRETION_EMAILS_RE = re.compile(r"^(.*@akretion\.com(\.br)?)$")


class CrossConnectServer(models.Model):
    _inherit = "cross.connect.server"

    @api.model
    def redirect_to_support(self):
        """Redirect to the support page"""
        # Any user with low rights may have the right to create tickets but can't
        # read cross.connect.server.
        self = self.sudo()
        server = self.env.ref("support.support_server")
        url = f"/cross_connect_server/{server.id}"
        params = {
            "origin_db": self.env.cr.dbname,
        }
        res_model = self.env.context.get("active_model")
        res_id = self.env.context.get("active_id")
        params["origin_url"] = (
            self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        )
        if res_model and res_id:
            record = self.env[res_model].browse(res_id)
            params["origin_name"] = record.name_get()[0][1]

            url_params = {
                "view_type": "form",
                "model": res_model,
                "id": res_id,
                "active_id": res_id,
                "cids": ",".join(str(x) for x in self.env.companies.ids),
            }

            action = self.env.context.get("params", {}).get("action")
            if not action:
                action = self.env["ir.actions.act_window"].search(
                    [("res_model", "=", res_model), ("view_mode", "ilike", "form")],
                    limit=1,
                )
                if action:
                    action = action.id
            if action:
                url_params["action"] = action

            params["origin_url"] += f"/web#{urlencode(url_params)}"

        redirect_params = {
            "action": "project_customer_access.action_view_all_task",
            "view_type": "form",
            **{
                f"project.task_default_{field}": value
                for field, value in params.items()
            },
        }

        final_params = {"redirect_url": f"/web#{urlencode(redirect_params)}"}
        url += "?" + urlencode(final_params)

        # Akretion users specific case
        if self.env.user.email and AKRETION_EMAILS_RE.match(self.env.user.email):
            redirect_params["action"] = "project.action_view_task"
            server_url = urlparse(server.server_url)
            server_url = server_url._replace(
                path="/web",
                fragment=urlencode(redirect_params),
            )
            url = server_url.geturl()
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }
