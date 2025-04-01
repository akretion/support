# Copyright 2024 Akretion
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json

from lxml import etree

from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    cross_connect_client_id = fields.Many2one("cross.connect.client")


class ProjectTask(models.Model):
    _inherit = "project.task"

    origin_url = fields.Char()
    origin_db = fields.Char()
    origin_name = fields.Char()

    def _get_customer_access_view_ids(self):
        form_id = self.env.ref("project_customer_access.view_task_form")
        kanban_id = self.env.ref("project_customer_access.view_task_kanban")
        search_id = self.env.ref("project_customer_access.view_task_search_form")
        return form_id | kanban_id | search_id

    def _get_editable_fields_customer(self):
        return ["name", "description", "is_urgent"]

    def _get_editable_fields_manager(self):
        return [
            "name",
            "description",
            "tag_ids",
            "stage_id",
            "project_id",
            "sprint_id",
            "is_urgent",
        ]

    def _get_readonly_value(self, field):
        field_name = field.attrib.get("name")

        if self.env.user.has_group("project_customer_access.group_manager"):
            return field_name not in self._get_editable_fields_manager()

        elif self.env.user.has_group("project_customer_access.group_customer"):
            if field_name == "project_id":
                # project_id must be readonly only after creation
                return [("create_date", "!=", False)]
            elif field_name in self._get_editable_fields_customer():
                # Allows the customers who are not manager to modify only their tasks
                return [("user_ids", "not in", self.env.user.id)]
            else:
                return True

        else:
            return True

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        res = super().get_view(view_id=view_id, view_type=view_type, **options)
        customer_access_view_ids = self._get_customer_access_view_ids()
        if view_id in customer_access_view_ids.ids:
            doc = etree.XML(res["arch"])
            if view_type in ["form", "kanban"]:
                for field in doc.xpath("//field[@name][not(ancestor::field)]"):
                    modifiers = json.loads(
                        field.attrib.get("modifiers", '{"readonly": false}')
                    )
                    if modifiers.get("readonly") is not True:
                        modifiers["readonly"] = self._get_readonly_value(field)

                    field.attrib["modifiers"] = json.dumps(modifiers)

            # List all accessible projects in filters for customers project users

            if view_type == "search":
                projects = self.env["project.project"].search([])
                node = doc.xpath("//search")[0]
                idx = node.index(node.xpath("//filter[@name='unassigned']")[0])
                for project in reversed(projects):
                    elem = etree.Element(
                        "filter",
                        string=project.name,
                        name=f"project_{project.id}",
                        domain=f"[('project_id', '=', {project.id})]",
                    )
                    node.insert(idx, elem)
                if projects:
                    node.insert(idx, etree.Element("separator"))

            res["arch"] = etree.tostring(doc, pretty_print=True)

        return res

    def write(self, values):
        if (
            self.env.user.has_group("project_customer_access.group_manager")
            and "project_id" in values
        ):
            # We need to give sudo access to the manager to be able to change project_id
            # on the task's timesheets even if they are not its own.
            self.env = self.sudo().env

        return super().write(values)
