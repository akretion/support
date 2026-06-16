# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo import fields, models


class CrossConnectClient(models.Model):
    _inherit = "cross.connect.client"

    project_ids = fields.One2many("project.project", "cross_connect_client_id")
