# Copyright 2016 Akretion (http://www.akretion.com)
# Benoit Guillot <benoit.guillot@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
# pylint: disable=W8106

import logging
import urllib

from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class ExternalTask(models.Model):
    _name = "external.task"
    _description = "external.task"

    def _get_select_project(self):
        config = self.env["support.account"]._get_config()
        return [
            (project["id"], project["name"])
            for project in config.get("projects", [])
            ]

    def _get_default_project(self):
        projects = self._get_select_project()
        if projects:
            return projects[0][0]

    name = fields.Char("Name", required=True)
    stage_id = fields.Many2one(
        'o2o.project.task.stage',
        'Stage'
        )
    description = fields.Html("Description")
    message_ids = fields.One2many(
        comodel_name="external.message", inverse_name="res_id"
    )
    create_date = fields.Datetime("Create Date", readonly=True)
    priority = fields.Selection(
        [("0", "Low"), ("1", "Normal"), ("2", "High")], default="1"
    )
    date_deadline = fields.Date("Date deadline", readonly=True)
    author_id = fields.Many2one("res.partner", string="Author", readonly=True)
    assignee_supplier_id = fields.Many2one(
        "res.partner", string="Resp. Externe", readonly=True
    )
    assignee_customer_id = fields.Many2one(
        "res.partner", string="Resp. Interne", readonly=True
    )
    origin_name = fields.Char()
    origin_url = fields.Char()
    origin_db = fields.Char()
    origin_model = fields.Char()
    project_id = fields.Selection(
        selection=_get_select_project,
        string="Project",
        default=_get_default_project,
        required=True,
    )
    color = fields.Integer(string="Color Index")
    tag_ids = fields.Many2many(comodel_name='o2o.project.tag', string='Tags')
    attachment_ids = fields.One2many(
        comodel_name="external.attachment", inverse_name="res_id"
    )
    message_attachment_count = fields.Integer("Attachment Count")
    planned_hours = fields.Float(string="Planned hours", readonly=True)
    planned_days = fields.Float(string="Planned days", readonly=True)
    invoiceable_days = fields.Float(string="Invoiceable days", readonly=True)
    estimate_step_name = fields.Char(string="Estimate Step", readonly=True)
    kanban_state = fields.Selection([
        ('normal', 'In Progress'),
        ('done', 'Ready'),
        ('blocked', 'Blocked')], string='Kanban State',
        copy=False, default='normal', required=True)
    sequence = fields.Integer()
    is_closed = fields.Boolean()

    @api.model
    def _call_odoo(self, method, params):
        return self.env["support.account"]._call_odoo("task", method, params)

    def _add_assignee_customer(self, vals, assignee_customer_id):
        if assignee_customer_id:
            partner = self.env["res.partner"].browse(assignee_customer_id)
            if not partner.user_ids:
                raise UserError(_("You can only assign ticket to your users"))
            else:
                vals["assignee_customer"] = self._get_partner_info(partner)

    @api.model
    def create(self, vals):
        vals = self._add_missing_default_values(vals)
        vals["author"] = self._get_author_info()
        if not vals.get("model_reference", False):
            vals["model_reference"] = ""
        self._add_assignee_customer(vals, vals.pop("assignee_customer_id", None))
        # avoid returning False in description because webservice expects a string
        if "description" in vals and not vals["description"]:
            vals["description"] = ""
        task_id = self._call_odoo("create", vals)
        return self.browse(task_id)

    def write(self, vals):
        params = {"ids": self.ids, "vals": vals, "author": self._get_author_info()}
        self._add_assignee_customer(params, vals.pop("assignee_customer_id", None))
        return self._call_odoo("write", params)

    def unlink(self):
        return True

    def copy(self, default):
        return self

    def read(self, fields=None, load="_classic_read"):
        tasks = self._call_odoo(
            "read", {"ids": self.ids, "fields": fields, "load": load}
        )
        partner_obj = self.env["res.partner"]
        for task in tasks:
            for key in ["author_id", "assignee_customer_id", "assignee_supplier_id"]:
                if key in fields:
                    task[key] = partner_obj._get_local_id_name(task[key])
            if "project_id" in fields:
                task["project_id"] = task["project_id"][0]
        return tasks

    @api.model
    def search(self, domain, offset=0, limit=0, order=None, count=False):
        result = self._call_odoo(
            "search",
            {
                "domain": domain,
                "offset": offset,
                "limit": limit,
                "order": order or "",
                "count": count,
            },
        )
        if count:
            return result
        else:
            return self.browse(result)

    @api.model
    def read_group(
        self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True
    ):
        res = self._call_odoo(
            "read_group",
            {
                "domain": domain,
                "fields": fields,
                "groupby": groupby or [],
                "offset": offset,
                "limit": limit,
                "orderby": orderby or "",
                "lazy": lazy,
            },
        )
        if self._context.get("no_empty_stage") and ["stage_id"] == groupby:
            return [item for item in res if item["stage_id_count"] > 0]
        return res

    def _message_get_suggested_recipients(self):
        result = {task.id: [] for task in self}
        return result

    def _get_author_info(self):
        return self._get_partner_info(self.env.user.partner_id)

    def _get_partner_info(self, partner):
        return {
            "uid": partner.id,
            "name": partner.name,
            "image": partner.image_1920.decode("utf-8") if partner.image_1920 else None,
            "email": partner.email or "",
            "mobile": partner.mobile or "",
            "phone": partner.phone or "",
        }

    # hack to make message post works (exists is checked in mail_message_post, in 
    # mail controllers)
    @api.returns('self')
    def exists(self):
        return self

    def message_post(self, body="", **kwargs):
        mid = self._call_odoo(
            "message_post",
            {"_id": self.id, "body": body, "author": self._get_author_info()},
        )
        return self.env["mail.message"].browse(["external/%s" % mid])

    @api.model
    def message_get(self, external_ids):
        messages = self._call_odoo("message_format", {"ids": external_ids})
        for message in messages:
            if "author_id" in message:
                message["author_id"] = self.env["res.partner"]._get_local_id_name(
                    message["author_id"]
                )
        return messages

    @api.model
    def message_fetch(self, domain, limit):
        messages = self._call_odoo("message_fetch", {"domain": domain, "limit": limit})
        for message in messages:
            if "author_id" in message:
                message["author_id"] = self.env["res.partner"]._get_local_id_name(
                    message["author_id"]
                )
        return messages

    def _get_mail_thread_data(self, request_list):
        res = self.env["mail.thread"]._get_mail_thread_data(request_list)
        # copied from mail module, needed because we do not inherits mail.thread
        # we need thos hasWriteAccess to enable the send message button on UI mail
        # message widget
        try:
            self.check_access_rights("write")
            self.check_access_rule("write")
            res['hasWriteAccess'] = True
        except AccessError:
            pass
        return res

    @api.model
    def default_get(self, fields):
        vals = super(ExternalTask, self).default_get(fields)
        if "from_model" in self._context and "from_id" in self._context:
            vals["model_reference"] = "{},{}".format(
                self._context["from_model"], self._context["from_id"]
            )
        if "from_action" in self._context:
            vals["action_id"] = self._context["from_action"]
        return vals

    def message_partner_info_from_emails(self, emails, link_mail=False):
        return []

    def _set_readonly_form_view(self, doc):
        for field in doc.iter("field"):
            env_fields = self._server_env_fields.keys()
            field_name = field.get("name")
            if field_name in env_fields:
                continue
            field.set("readonly", "1")
            field.set("modifiers", json.dumps({"readonly": True}))

    def _update_form_view_for_manager(self, arch, view_type):
        if view_type != "form":
            return arch
        is_manager = self.env.user.has_group("project_api_client.group_support_manager")
        if not is_manager:
            return arch
        for field in arch.iter("field"):
            editable_fields = ["tag_ids", "project_id", "assignee_customer_id", "priority"]
            if field.get("name") in editable_fields:
                field.set("readonly", "0")
        project_groups = arch.xpath("//group[@name='project']")
        group_el = project_groups and project_groups[0]
        # remove invisible part on creation for manager
        group_el.attrib.pop("attrs", None)
        return arch

    def _update_search_view(self, arch, view_type):
        if view_type == "search":
            node = arch.xpath("//search")[0]
            for project_id, project_name in self._get_select_project():
                elem = etree.Element(
                    "filter",
                    string=project_name,
                    name=f"project_{project_id}",
                    domain=f"[('project_id', '=', {project_id})]",
                )
                node.append(elem)
            node.append(etree.Element("separator"))
            for tag in self.env['o2o.project.tag'].search([]):
                elem = etree.Element(
                    "filter",
                    string=tag.name,
                    name="tag_%s" % tag.id,
                    domain=f"[('tag_ids', '=', {tag.id})]",
                )
                node.append(elem)
                node.append(etree.Element("separator"))
            node = arch.xpath("//filter[@name='my_task']")
            if node:
                node[0].attrib["domain"] = (
                    "[('assignee_customer_id.customer_uid', '=', %s)]"
                    % self.env.user.partner_id.id
                )
        return arch

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id=view_id, view_type=view_type, **options)
        arch = self._update_form_view_for_manager(arch, view_type)
        arch = self._update_search_view(arch, view_type)
        return arch, view

    def _get_view_cache_key(self, view_id=None, view_type="form", **options):
        res = super()._get_view_cache_key(
            view_id=view_id, view_type=view_type, **options
        )
        res += (self.env.user.has_group("project_api_client.group_support_manager"),)
        return res


class ExternalMessage(models.Model):
    _name = "external.message"
    _description = "external.message"

    res_id = fields.Many2one(comodel_name="external.task")


class MailMessage(models.Model):
    _inherit = "mail.message"

    @api.model
    def _message_fetch(self, domain, max_id=None, min_id=None, limit=30):
        if any(["external.task" in item for item in domain]):
            new_domain = [item for item in domain if "external.task" not in item]
            return self.env["external.task"].message_fetch(new_domain, limit=limit)
        else:
            return super()._message_fetch(
                domain, max_id=max_id, min_id=min_id, limit=limit
            )

    def message_format(self, format_reply=True):
        ids = self.ids
        if ids and isinstance(ids[0], str) and "external" in ids[0]:
            external_ids = [int(mid.replace("external/", "")) for mid in ids]
            return self.env["external.task"].message_get(external_ids)
        else:
            return super().message_format(format_reply=format_reply)

    def set_message_done(self):
        for _id in self.ids:
            if isinstance(_id, str) and "external" in _id:
                return True
        else:
            return super().set_message_done()


class IrActionActWindows(models.Model):
    _inherit = "ir.actions.act_window"

    def _set_origin_in_context(self, action):
        ctx = self._context

        def get_previous_action(model):
            # FIXME Not sure when/if this params exist some times nor in which case.
            previous_action = ctx.get("params") and ctx["params"].get("action")
            # We avoid searching an action by default because it could contain
            # some context making the url to fail. Example, a sale.order action
            # which has this context : 'search_default_team_id': [active_id]
            # would fail because the active_id we pass is actually the one from
            # a sale order...
            return previous_action

        context = {"default_origin_db": self._cr.dbname}
        ICP = self.env["ir.config_parameter"].sudo()
        base_url = ICP.get_param("web.base.url")
        _id = ctx.get("active_id")
        model = ctx.get("active_model")
        if _id and model:
            record = self.env[model].browse(_id)
            context["default_origin_name"] = record.display_name
            context["default_origin_model"] = model
            vals_path = {
                "view_type": "form",
                "model": model,
                "id": _id,
                # some redirections require 'active_id' i.e. 'sale.order'
                "active_id": _id,
                "cids": ",".join(str(x) for x in self.env.companies.ids),
            }
            previous_action = get_previous_action(model)
            if previous_action:
                # 'action' or 'menu_id' key prevent redirection fails
                # when website module is installed
                vals_path["action"] = previous_action
            path = urllib.parse.urlencode(vals_path)
            context["default_origin_url"] = "{}/web#{}".format(base_url, path)
        action["context"] = context

    def _set_default_project(self, action):
        # we add a try/except to avoid raising a pop-up want odoo server
        # is down
        try:
            projects = self.env["external.task"]._get_select_project()
            if projects:
                key = "search_default_project_%s" % projects[0][0]
                action["context"] = {key: 1}
        except Exception:
            _logger.warning("Fail to add the default project")

    @api.model
    def _update_action(self, action):
        account = self.env["support.account"]._get()
        if not account:
            return
        action_support = self.env.ref("project_api_client.action_helpdesk", False)
        if action_support and action["id"] == action_support.id:
            self._set_origin_in_context(action)
        action_external_task = self.env.ref(
            "project_api_client.action_view_external_task", False
        )
        if action_external_task and action["id"] == action_external_task.id:
            self._set_default_project(action)

    def read(self, fields=None, load="_classic_read"):
        res = super(IrActionActWindows, self).read(fields=fields, load=load)
        for action in res:
            self._update_action(action)
        return res


class ExternalAttachment(models.Model):
    _name = "external.attachment"
    _description = "external.attachment"

    res_id = fields.Many2one(comodel_name="external.task")
    name = fields.Char()
    datas = fields.Binary()
    res_model = fields.Char(default="project.task")
    datas_fname = fields.Char()
    type = fields.Char(default="binary")
    mimetype = fields.Char()

    @api.onchange("datas_fname")
    def _file_change(self):
        if self.datas_fname:
            self.name = self.datas_fname

    def read(self, fields=None, load="_classic_read"):
        return self._call_odoo(
            "read", {"ids": self.ids, "fields": fields, "load": load}
        )

    @api.model
    def _call_odoo(self, method, params):
        return self.env["support.account"]._call_odoo("attachment", method, params)

    def exists(self):
        return self.browse(self._call_odoo("exists", {"ids": self.ids}))
