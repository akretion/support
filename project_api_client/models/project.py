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

    def _get_mail_thread_data(self, request_list):
        # copied from mail/models/mail_thread.py:3323
        # TODO: Fix chatter read
        res = {'hasWriteAccess': False, 'hasReadAccess': True}
        if not self:
            res['hasReadAccess'] = False
        return res

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

    def message_post(self, body="", **kwargs):
        mid = self._call_odoo(
            "message_post",
            {"_id": self.id, "body": body, "author": self._get_author_info()},
        )
        return "external/%s" % mid

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

    def fields_view_get(
        self, view_id=None, view_type=False, toolbar=False, submenu=False
    ):
        res = super(ExternalTask, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu
        )
        doc = etree.XML(res["arch"])
        if view_type == "form":
            for node in doc.xpath("//field[@name='message_ids']"):
                options = safe_eval(node.get("options", "{}"))
                options.update({"display_log_button": False})
                node.set("options", repr(options))
        elif view_type == "search":
            node = doc.xpath("//search")[0]
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
            node = doc.xpath("//filter[@name='my_task']")
            if node:
                node[0].attrib["domain"] = (
                    "[('assignee_customer_id.customer_uid', '=', %s)]"
                    % self.env.user.partner_id.id
                )
        res["arch"] = etree.tostring(doc, pretty_print=True)
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


class ExternalMessage(models.Model):
    _name = "external.message"
    _description = "external.message"

    res_id = fields.Many2one(comodel_name="external.task")


class MailMessage(models.Model):
    _inherit = "mail.message"

    @api.model
    def message_fetch(self, domain, limit=20, moderated_channel_ids=None):
        if any(["external.task" in item for item in domain]):
            new_domain = [item for item in domain if "external.task" not in item]
            return self.env["external.task"].message_fetch(new_domain, limit=limit)
        else:
            return super().message_fetch(
                domain, limit=limit, moderated_channel_ids=moderated_channel_ids
            )

    def message_format(self, **kwargs):
        # From v15 this method has `format_reply=True` as kwargs
        ids = self.ids
        if ids and isinstance(ids[0], str) and "external" in ids[0]:
            external_ids = [int(mid.replace("external/", "")) for mid in ids]
            return self.env["external.task"].message_get(external_ids)
        else:
            return super(MailMessage, self).message_format(kwargs)

    def set_message_done(self):
        for _id in self.ids:
            if isinstance(_id, str) and "external" in _id:
                return True
        else:
            return super(MailMessage, self).set_message_done()


class IrActionActWindows(models.Model):
    _inherit = "ir.actions.act_window"

    def _set_origin_in_context(self, action):
        context = {"default_origin_db": self._cr.dbname}
        ICP = self.env["ir.config_parameter"].sudo()
        base_url = ICP.get_param("web.base.url")
        _id = self._context.get("active_id")
        model = self._context.get("active_model")
        if _id and model:
            record = self.env[model].browse(_id)
            context["default_origin_name"] = record.display_name
            context["default_origin_model"] = model
            path = urllib.parse.urlencode(
                {
                    "view_type": "form",
                    "model": model,
                    "id": _id,
                    "cids": ",".join(str(x) for x in self.env.companies.ids),
                }
            )
            context["default_origin_url"] = "{}#{}".format(base_url, path)
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
