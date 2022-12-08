# Copyright 2022 Akretion (https://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class O2OProjectTaskStage(models.Model):
    _name = 'o2o.project.task.stage'
    _description = 'O2O Project Task Stage'

    _order = "sequence"

    name = fields.Char()
    current_sprint = fields.Boolean()
    sequence = fields.Integer()
