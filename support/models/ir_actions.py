# Copyright 2025 Akretion (http://www.akretion.com).
# @author Florian Mounier <florian.mounier@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class IrActions(models.Model):
    _inherit = "ir.actions.actions"

    @api.model
    def get_bindings(self, model_name):
        """Add support action to every model"""
        res = super().get_bindings(model_name)
        support_server = self.env.ref("support.akretion_erp", raise_if_not_found=False) or self.env["cross.connect.server"]
        support_groups = self.env.user.groups_id & support_server.group_ids
        if support_groups:
            action_id = "support.cross_connect_support"
            if "action" in res:
                if action_id not in [act.get("xml_id") for act in res["action"]]:
                    res["action"].append(self._for_xml_id(action_id))
            else:
                res["action"] = [self._for_xml_id(action_id)]

        return res
