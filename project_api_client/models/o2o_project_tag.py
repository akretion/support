# Copyright 2022 Akretion (https://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class O2OProjectTag(models.Model):
    _name = 'o2o.project.tag'
    _description = 'O2O Project Tag'

    name = fields.Char(required=True)
    color = fields.Integer(string="Color Index")
