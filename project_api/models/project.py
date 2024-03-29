# Copyright 2018 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, tools


class ProjectProject(models.Model):
    _inherit = "project.project"

    customer_project_name = fields.Char(
        help="Name that will appear on customer support menu", index=True
    )
    subscribe_assigned_only = fields.Boolean(
        string="Subscribe assigned only",
        help="When a user get assigned, unscubscribe automaticaly other users",
    )

    def _get_customer_project_name(self):
        return self.customer_project_name or self.name


class ProjectTask(models.Model):
    _inherit = "project.task"

    stage_name = fields.Char(
        "Stage Label",
        compute="_compute_stage_name",
        inverse="_inverse_stage_name",
        store=True,
    )
    author_id = fields.Many2one(
        "res.partner",
        default=lambda self: self.env.user.partner_id.id,
        string="Create By",
    )
    partner_id = fields.Many2one(
        related="project_id.partner_id", readonly=True, store=True
    )
    user_id = fields.Many2one(default=False)
    assignee_supplier_id = fields.Many2one(
        "res.partner", related="user_id.partner_id", store=True
    )
    assignee_customer_id = fields.Many2one(
        "res.partner", string="Assigned Customer", tracking=True
    )
    origin_name = fields.Char()
    origin_url = fields.Char()
    origin_db = fields.Char()
    origin_model = fields.Char()
    technical_description = fields.Html()
    support_attachment_ids = fields.One2many(
        comodel_name="ir.attachment",
        inverse_name="res_id",
        domain=[("res_model", "=", "project.task")],
    )
    functional_area = fields.Selection(
        selection=[
            ("purchase", "Purchase"),
            ("account", "Account"),
            ("sale", "Sale"),
            ("stock", "Stock"),
            ("crm", "Crm"),
            ("procurement", "Procurement"),
            ("management", "Management"),
        ],
        string="Functional Area",
    )
    customer_report = fields.Html(compute="_compute_customer_report", store=True)
    customer_kanban_report = fields.Html(
        compute="_compute_customer_kanban_report", store=True
    )
    priority = fields.Selection(selection_add=[("2", "Very Important")])
    estimate_step_name = fields.Char(related="estimate_step_id.name")

    # Add your own logic for computing this field
    # in Akretion case is done by subcontractor module
    invoiceable_days = fields.Float(string="Invoiceable days", readonly=True)

    def _build_customer_report(self):
        """This method allow you to return an html that will be show on client side
        This avoid having too much logic and too much module with dependency on client
        side.
        You just need to hack whatever you want in this html on server side and then
        all of your customer will see it"""
        return ""

    def _build_customer_kanban_report(self):
        """This method allow you to return an html that will be show on client side
        This avoid having too much logic and too much module with dependency on client
        side.
        You just need to hack whatever you want in this html on server side and then
        all of your customer will see it"""
        return ""

    def _compute_customer_report(self):
        for record in self:
            record.customer_report = record._build_customer_report()

    def _compute_customer_kanban_report(self):
        for record in self:
            record.customer_kanban_report = record._build_customer_kanban_report()

    @api.depends("stage_id")
    def _compute_stage_name(self):
        for task in self:
            task.stage_name = task.stage_id.name

    def _inverse_stage_name(self):
        for task in self:
            stages = self.env["project.task.type"].search(
                [
                    ("project_ids", "in", [task.project_id.id]),
                    ("name", "=", task.stage_name),
                ]
            )
            if stages:
                task.stage_id = stages[0].id

    @api.returns("self", lambda value: value.id)
    def message_post(
        self,
        *,
        body="",
        subject=None,
        message_type="notification",
        email_from=None, author_id=None, parent_id=False,
        subtype_xmlid=None, subtype_id=False, partner_ids=None, channel_ids=None,
        attachments=None, attachment_ids=None,
        add_sign=True, record_name=False, **kwargs
    ):
        if self._context.get("force_message_author_id"):
            author_id = self._context["force_message_author_id"]
        return super().message_post(
        body=body,
        subject=subject,
        message_type=message_type,
        email_from=email_from, author_id=author_id, parent_id=parent_id,
        subtype_xmlid=subtype_xmlid, subtype_id=subtype_id, partner_ids=partner_ids, channel_ids=channel_ids,
        attachments=attachments, attachment_ids=attachment_ids,
        add_sign=add_sign, record_name=record_name, **kwargs
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.pop("partner_id", None)  # readonly
        return super().create(vals_list)

    def write(self, vals):
        vals.pop("partner_id", None)  # readonly
        if "user_id" in vals and self.project_id.subscribe_assigned_only:
            followers = self.message_follower_ids.mapped("partner_id")
            unsubscribe_users = self.env["res.users"].search(
                [("partner_id", "in", followers.ids), ("id", "!=", vals["user_id"])]
            )
            partner_ids = [user.partner_id.id for user in unsubscribe_users]
            self.message_unsubscribe(partner_ids=partner_ids)
        return super().write(vals)

    def _message_auto_subscribe(self, updated_values, followers_existing_policy='skip'):
        res = super()._message_auto_subscribe(
            updated_values, followers_existing_policy=followers_existing_policy)
        if updated_values.get("author_id"):
            self.message_subscribe([updated_values["author_id"]])
        if updated_values.get("assignee_customer_id"):
            self.message_subscribe([updated_values["assignee_customer_id"]])
        return res

    def message_get_suggested_recipients(self):
        # we do not need this feature
        return {}

    @api.model
    def message_new(self, msg, custom_values=None):
        partner_email = tools.email_split(msg["from"])[0]
        # Automatically create a partner
        if not msg.get("author_id"):
            alias = tools.email_split(msg["to"])[0].split("@")[0]
            project = self.env["project.project"].search([("alias_name", "=", alias)])
            partner = self.env["res.partner"].create(
                {
                    "parent_id": project.partner_id.id,
                    "name": partner_email.split("@")[0],
                    "email": partner_email,
                }
            )
            msg["author_id"] = partner.id
        if custom_values is None:
            custom_values = {}
        custom_values.update(
            {"description": msg["body"], "author_id": msg["author_id"]}
        )
        return super().message_new(msg, custom_values=custom_values)

    def _read_group_stage_ids(self, stages, domain, order):
        project_ids = self._context.get("stage_from_project_ids")
        if project_ids:
            projects = self.env["project.project"].browse(project_ids)
            stages |= projects.mapped("type_ids")
        return super()._read_group_stage_ids(stages, domain, order)
