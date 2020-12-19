# © 2015 David BEAL @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, models

# Duplicate from module project_model_to_task
# to create an external_task instead of a project_task


class IrActions(models.Model):
    _inherit = "ir.actions.actions"

    @api.model
    def get_bindings(self, model_name):
        """ Add an action to all Model objects of the ERP """
        res = super(IrActions, self).get_bindings(model_name)
        user_groups = self.env.user.groups_id
        action = self.env.ref("project_api_client.action_helpdesk")
        action_groups = getattr(action, "groups_id", ())
        if action_groups and action_groups & user_groups:
            res["action"].append(action.read()[0])
        return res
