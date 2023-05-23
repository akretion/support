# © 2015 David BEAL @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, models

# Duplicate from module project_model_to_task
# to create an external_task instead of a project_task


class IrActions(models.Model):
    _inherit = "ir.actions.actions"

    @api.model
    def get_bindings(self, model_name):
        """Add an action to all Model objects of the ERP"""
        res = super(IrActions, self).get_bindings(model_name)
        if self.env.user.has_group("project_api_client.group_support_user"):
            xml_id = "project_api_client.action_helpdesk"
            if "action" in res and xml_id not in [
                act.get("xml_id") for act in res["action"]
            ]:
                res["action"].append(self.env.ref(xml_id).sudo().read()[0])
        return res
