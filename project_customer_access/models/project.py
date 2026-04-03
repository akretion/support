# Copyright 2024 Akretion
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from lxml import etree

from odoo import _, api, exceptions, fields, models
from odoo.fields import first


class ProjectProject(models.Model):
    _inherit = "project.project"

    @api.depends("cross_connect_client_id")
    def _compute_is_default_support_project(self):
        for project in self:
            if (
                not project.cross_connect_client_id
                and project.is_default_support_project
            ):
                project.is_default_support_project = False

    cross_connect_client_id = fields.Many2one("cross.connect.client")
    is_default_support_project = fields.Boolean(
        compute="_compute_is_default_support_project",
        store=True,
        readonly=False,
        help="This project will be the one set by default when an external user "
        "create a task",
    )

    @api.constrains("cross_connect_client_id", "is_default_support_project")
    def _check_unique_default_project(self):
        for cross_connect in self.cross_connect_client_id:
            default_project = cross_connect.project_ids.filtered(
                lambda pr: pr.is_default_support_project
            )
            if len(default_project) > 1:
                raise exceptions.ValidationError(
                    _("You can set only one default project per customer")
                )


class ProjectTask(models.Model):
    _inherit = "project.task"

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if self.env.user.cross_connect_client_id:
            default_project = (
                self.env.user.cross_connect_client_id.project_ids.filtered(
                    lambda pr: pr.is_default_support_project
                )
                or first(self.env.user.cross_connect_client_id.project_ids)
            )
            if default_project:
                res["project_id"] = default_project.id
                res["stage_id"] = self.stage_find(
                    default_project.id, [("fold", "=", False)]
                )
        return res

    origin_url = fields.Char()
    origin_db = fields.Char()
    origin_name = fields.Char()
    cross_connect_client_id = fields.Many2one(
        related="project_id.cross_connect_client_id"
    )
    user_ids = fields.Many2many(
        domain="["
        "('share', '=', False), "
        "('active', '=', True), "
        "'|', ('cross_connect_client_id', '=', False), "
        "('cross_connect_client_id', '=', cross_connect_client_id)"
        "]"
    )
    customer_user_ids = fields.Many2many(
        "res.users",
        relation="project_task_customer_user_rel",
        column1="task_id",
        column2="user_id",
        domain="[('cross_connect_client_id', '=', cross_connect_client_id)]",
        tracking=True,
    )

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
            "priority",
            "customer_user_ids",
        ]

    def _get_readonly_value(self, field):
        field_name = field.attrib.get("name")

        if self.env.user.has_group("project_customer_access.group_manager"):
            return field_name not in self._get_editable_fields_manager()

        elif self.env.user.has_group("project_customer_access.group_customer"):
            if field_name == "project_id":
                # project_id must be readonly only after creation
                return "create_date != False"
            elif field_name in self._get_editable_fields_customer():
                # Allows the customers who are not manager to modify only their tasks
                return f"create_date != False and create_uid != {self.env.user.id}"
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
                    readonly = field.attrib.get("readonly")
                    if not readonly or readonly == "0" or readonly == "False":
                        value = self._get_readonly_value(field)
                        field.attrib["readonly"] = (
                            str(value) if isinstance(value, bool) else value
                        )

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
