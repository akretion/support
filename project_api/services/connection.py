# Copyright 2019 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo.addons.component.core import Component


class ConnectionService(Component):
    _inherit = "base.rest.service"
    _name = "external.connection.service"
    _collection = "project.project"
    _usage = "connection"

    def test(self):
        return {"success": "ok"}

    def _validator_test(self):
        return {}
