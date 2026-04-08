# Copyright 2026 Akretion (http://www.akretion.com).
# @author Florian Mounier <florian.mounier@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import api, models
from odoo.http import request


class ProjectTask(models.Model):
    _inherit = "project.task"

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        session = request.session
        if session and session.get("support_default_params"):
            defaults.update(session.pop("support_default_params"))
        return defaults
