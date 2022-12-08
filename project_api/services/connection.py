# Copyright 2019 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo.addons.component.core import Component


class ConnectionService(Component):
    _inherit = "base.rest.service"
    _name = "external.connection.service"
    _collection = "project.project"
    _usage = "connection"

    @property
    def partner(self):
        return self.work.partner

    def test(self):
        return {"success": "ok"}

    def config(self):
        config = {"projects": []}
        projects = self.partner.help_desk_project_id
        for project in self.env["project.project"].search([
            ("partner_id", "=", self.partner.id),
            ]):
            config["projects"].append({
                "id": project.id,
                "name": project.name,
                "tags": [{"id": tag.id, "name": tag.name, "color": tag.color} for tag in project.tag_ids],
                "stages": [{"id": st.id, "name": st.name, "sequence": st.sequence} for st in project.type_ids],
            })
        return config

    def _validator_test(self):
        return {}

    def _validator_config(self):
        return {}


