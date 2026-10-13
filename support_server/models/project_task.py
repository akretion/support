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
        # request is not bound outside of an HTTP request (tests, import
        # scripts, cron jobs...): `bool(request)` is False in that case.
        if request:
            params = request.session.pop("support_default_params", None)
            if params:
                defaults.update(params)
        return defaults
