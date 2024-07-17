# Copyright 2016 Akretion (http://www.akretion.com)
# Benoit Guillot <benoit.guillot@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.http import request
############
from fastapi import APIRouter, Depends
from odoo.addons.fastapi.dependencies import (
    authenticated_partner_env,
    authenticated_partner,
    fastapi_endpoint_id,
    odoo_env,
)
from typing import Annotated
from ..schemas.partner import PartnerReadInput
from ..schemas.attachment import AttachmentReadInput, AttachmentExistsInput, AttachmentDownloadInput
from ..schemas.task import TaskSearchInput, TaskReadInput, TaskReadGroupInput, TaskCreateInput, TaskWriteInput, TaskMessageFormatInput, TaskGetMessageInput, TaskMessageFetchInput, TaskMessagePostInput
from odoo.api import Environment
from odoo.osv import expression
from ..dependencies import version


_logger = logging.getLogger(__name__)

support_api_router = APIRouter()


@support_api_router.post(
    "/connection/config",
)
def connection_config(
    env: Annotated[api.Environment, Depends(authenticated_partner_env)],
    partner: Annotated["ResPartner", Depends(authenticated_partner)],
):
    config = {"projects": []}
    for project in env["project.project"].search([
        ("partner_id", "=", partner.id),
        ("customer_display", "=", True)
    ]):
        config["projects"].append({
            "id": project.id,
            "name": project.name,
            "tags": [{"id": tag.id, "name": tag.name, "color": tag.color} for tag in project.tag_ids],
            "stages": [{"id": st.id, "name": st.name, "sequence": st.sequence} for st in project.type_ids],
        })
    return config


@support_api_router.post(
    "/connection/test",
    dependencies=[Depends(authenticated_partner)],
)
def connection_test():
    return {"success": "ok"}

# partner
@support_api_router.post(
    "/partner/search",
)
def partner_search(
    env: Annotated[api.Environment, Depends(authenticated_partner_env)],
    partner: Annotated["ResPartner", Depends(authenticated_partner)],
):
    return (
        env["res.partner"]
        .sudo()
        .search([("user_ids.active", "=", True), ("user_ids.share", "=", False)])
        .ids
    )


@support_api_router.post(
    "/partner/read",
    dependencies=[Depends(authenticated_partner)],
)
def partner_read(
    data: PartnerReadInput,
    env: Environment = Depends(odoo_env),
):
    """All res.user are exposed to this read only api"""
    partner = env["res.partner"].browse(data.uid)
    if partner.sudo().user_ids:
        image = partner.image_1024
        if image and not isinstance(str, type(image)):
            image = image.decode("utf-8")
        update_date = partner.write_date or partner.create_date
        res = {
            "name": partner.name,
            "uid": data.uid,
            "image": image or "",
            "update_date": fields.Datetime.to_string(update_date),
        }
        return res
    else:
        raise AccessError(_("You can not read information about this partner"))


# attachment
@support_api_router.post(
    "/attachment/read",
)
def attachment_read(
    data: AttachmentReadInput,
    env: Annotated[api.Environment, Depends(authenticated_partner_env)],
    partner: Annotated["ResPartner", Depends(authenticated_partner)],
):
    tasks = env["project.task"].search(
        [("project_id.partner_id", "=", partner.id), ("project_id.customer_display", "=", True)]
    )
    # compatibility with project_api_client <= 12
    # we could maybe remove datas_fname from all api_client version instead
    # maybe for next version
    att_fields = data.fields
    if "datas_fname" in att_fields:
        if not "name" in att_fields:
            att_fields.append("name")
        att_fields.remove("datas_fname")
    attachments = env["ir.attachment"].search(
        [
            ("id", "in", data.ids),
            ("res_id", "in", tasks.ids),
            ("res_model", "=", "project.task"),
        ]
    )
    attachments = attachments.read(fields=att_fields, load=data.load)
    for attachment in attachments:
        if attachment.get("name"):
            attachment["datas_fname"] = attachment["name"]
    if attachments:
        for attachment in attachments:
            if "datas" in attachment:
                attachment["datas"] = attachment["datas"].decode("utf-8")
            for date_field in ["write_date", "create_date"]:
                if date_field in attachment:
                    attachment[date_field] = fields.Datetime.to_string(
                        attachment[date_field]
                    )
        return attachments
    return []

    def exists(self, ids):
        return self.env["ir.attachment"].browse(ids).exists().ids


@support_api_router.post(
    "/attachment/exists",
)
def attachment_read(
    data: AttachmentExistsInput,
    env: Annotated[api.Environment, Depends(authenticated_partner_env)],
    partner: Annotated["ResPartner", Depends(authenticated_partner)],
):
    return env["ir.attachment"].browse(data.ids).exists().ids


@support_api_router.post(
    "/attachment/download_url",
)
def attachment_download_url(
    data: AttachmentDownloadInput,
    env: Annotated[api.Environment, Depends(authenticated_partner_env)],
    partner: Annotated["ResPartner", Depends(authenticated_partner)],
):
    tasks = env["project.task"].search(
        [("project_id.partner_id", "=", partner.id), ("project_id.customer_display", "=", True)]
    )
    attachment = env["ir.attachment"].search(
        [
            ("id", "=", data.attachment_id),
            ("res_id", "in", tasks.ids),
            ("res_model", "=", "project.task"),
        ]
    )
    if not attachment:
        url = ""
    else:
        base_url = env["ir.config_parameter"].sudo().get_param("web.base.url")
        token = attachment.generate_access_token()[0]
        url = ("%(base_url)s/web/content/?id=%(attach_id)s&download=true"
              "&filename=%(filename)s&access_token=%(token)s") % {"base_url": base_url, "attach_id": data.attachment_id, "filename": attachment.name, "token": token}
    return url


# Task
@support_api_router.post(
    "/task/search",
)
def task_search(
    data: TaskSearchInput,
    env: Annotated[api.Environment, Depends(authenticated_partner_env)],
    partner: Annotated["ResPartner", Depends(authenticated_partner)],
):
    domain = [("project_id.partner_id", "=", partner.id), ("project_id.customer_display", "=", True)] + data.domain
    tasks = env["project.task"].search(
        domain, offset=data.offset, limit=data.limit, order=data.order, count=data.count
    )
    if tasks:
        if data.count:
            # count will return the number of task in the tasks variable
            return tasks
        return tasks.ids
    return []


@support_api_router.post(
    "/task/read",
)
def task_read(
    data: TaskReadInput,
    version: Annotated[str, Depends(version)],
    env: Annotated[api.Environment, Depends(authenticated_partner_env)],
    partner: Annotated["ResPartner", Depends(authenticated_partner)],
):
    tasks = env["project.task"].search(
        [("id", "in", data.ids), ("project_id.partner_id", "=", partner.id)]
    )
    tasks = tasks.read(fields=data.fields, load=data.load)
    if tasks:
        for task in tasks:
            if "create_date" in task:
                task["create_date"] = fields.Datetime.to_string(
                    task["create_date"]
                )
            if "message_ids" in task:
                messages = env["mail.message"].search(
                    [
                        ("id", "in", task["message_ids"]),
                        "|",
                        ("subtype_id.internal", "=", False),
                        ("subtype_id", "=", False),
                    ]
                )
                task["message_ids"] = ["external/%s" % mid for mid in messages.ids]
            for key in [
                "author_id",
                "assignee_customer_id",
                "assignee_supplier_id",
            ]:

                if key in task:
                    task[key] = env["support.task.api.helper"]._map_partner_read_to_data(task[key])
                    # TODO
            if version < "2.0":
                if "tag_ids" in task:
                    task["tag_ids"] = task["tag_ids"] and task["tag_ids"][0] or False
                    if "color" in task:
                        if task["tag_ids"]:
                            task["color"] = (
                                self.env["project.tags"]
                                .search([("id", "=", task["tag_ids"])])
                                .color
                            )
                        else:
                            task["color"] = 0
        return tasks
    return []



@support_api_router.post(
    "/task/read_group",
)
def task_read_group(
    data: TaskReadGroupInput,
    env: Annotated[api.Environment, Depends(authenticated_partner_env)],
    partner: Annotated["ResPartner", Depends(authenticated_partner)],
):        
    domain = [("project_id.partner_id", "=", partner.id), ("project_id.customer_display", "=", True)] + data.domain
    groupby = data.groupby
    fields = data.fields
    task_obj = env["project.task"]
    group_by_stage_name = "stage_name" in groupby[0]
    if group_by_stage_name or "stage_id" in groupby[0]:
        project_ids = env["support.task.api.helper"]._get_all_project_ids_from_domain(partner, domain)
        task_obj = task_obj.with_context(stage_from_project_ids=project_ids)
    if group_by_stage_name:
        groupby[0] = "stage_id"
        fields[fields.index("stage_name")] = "stage_id"
    groups = task_obj.read_group(
        domain,
        fields,
        groupby,
        offset=data.offset,
        limit=data.limit,
        orderby=data.orderby,
        lazy=data.lazy,
    )
    if group_by_stage_name:
        for group in groups:
            group["stage_name"] = group.pop("stage_id")[1]._value
            group["stage_name_count"] = group.pop("stage_id_count")
    # TODO find a better way to resolve lazy value
    for group in groups:
        if "stage_id" in group:
            group["stage_id"] = (group["stage_id"][0], group["stage_id"][1]._value)
    return groups



@support_api_router.post(
    "/task/create",
)
def task_create(
    data: TaskCreateInput,
    version: Annotated[str, Depends(version)],
    env: Annotated[api.Environment, Depends(authenticated_partner_env)],
    partner: Annotated["ResPartner", Depends(authenticated_partner)],
):        
    assignee_customer_data = data.assignee_customer
    author_data = data.author
    # TODO get vals as dict...
    vals = data.model_dump(exclude_none=True)
    if assignee_customer_data:
        vals["assignee_customer_id"] = env["support.task.api.helper"]._get_partner(partner, assignee_customer_data.model_dump()).id
        vals.pop("assignee_customer")
    author = env["support.task.api.helper"]._get_partner(partner, author_data.model_dump())
    vals.pop("author")
    if not vals.get("project_id"):
        vals["project_id"] = partner.help_desk_project_id.id
    vals["author_id"] = author.id
    if version < "2.0":
        if vals.get("tag_ids"):
            vals["tag_ids"] = [(6, 0, [vals["tag_ids"]])]

    vals = env["support.task.api.helper"]._manage_attachment_vals(vals)
    task = (
        env["project.task"]
        .with_context(force_message_author_id=author.id)
        .create(vals)
    )
    return task.id


@support_api_router.post(
    "/task/write",
)
def task_write(
    data: TaskWriteInput,
    version: Annotated[str, Depends(version)],
    env: Annotated[api.Environment, Depends(authenticated_partner_env)],
    partner: Annotated["ResPartner", Depends(authenticated_partner)],
):        
    author = env["support.task.api.helper"]._get_partner(partner, data.author.model_dump())
    tasks = env["project.task"].search(
        [("id", "in", data.ids), ("project_id.partner_id", "=", partner.id)]
    )
    vals = data.vals.model_dump(exclude_none=True)
    if len(tasks) < len(data.ids):
        raise AccessError(_("You do not have the right to modify this records"))
    if data.assignee_customer:
        vals["assignee_customer_id"] = env["support.task.api.helper"]._get_partner(partner, data.assignee_customer.model_dump()).id
    if version < "2.0":
        if "tag_ids" in vals:
            vals["tag_ids"] = [(6, 0, [vals["tag_ids"]])]
    vals = env["support.task.api.helper"]._manage_attachment_vals(vals)
    return tasks.with_context(force_message_author_id=author.id).write(vals)


@support_api_router.post(
    "/task/message_format",
)
def task_message_format(
    data: TaskMessageFormatInput,
    env: Annotated[api.Environment, Depends(authenticated_partner_env)],
    partner: Annotated["ResPartner", Depends(authenticated_partner)],
):        
    return env["support.task.api.helper"].message_format(partner, data.ids)


@support_api_router.post(
    "/task/get_message",
)
def task_get_message(
    data: TaskGetMessageInput,
    env: Annotated[api.Environment, Depends(authenticated_partner_env)],
    partner: Annotated["ResPartner", Depends(authenticated_partner)],
):        
    messages = env["mail.message"].message_read(
        ids=json.loads(data.ids),
        domain=json.loads(data.domain),
        message_unload_ids=json.loads(data.message_unload_ids),
        thread_level=data.thread_level,
        parent_id=data.parent_id,
        limit=data.limit,
    )
    if messages:
        return messages
    return []


@support_api_router.post(
    "/task/message_fetch",
)
def task_message_fetch(
    data: TaskMessageFetchInput,
    env: Annotated[api.Environment, Depends(authenticated_partner_env)],
    partner: Annotated["ResPartner", Depends(authenticated_partner)],
):        
    domain = expression.AND(
        [
            data.domain,
            [
                ("subtype_id", "!=", env.ref("mail.mt_note").id),
                ("model", "=", "project.task"),
            ],
        ]
    )
    messages = env["mail.message"].search(domain)
    return env["support.task.api.helper"].message_format(partner, messages.ids)


@support_api_router.post(
    "/task/message_post",
)
def task_message_post(
    data: TaskMessagePostInput,
    env: Annotated[api.Environment, Depends(authenticated_partner_env)],
    partner: Annotated["ResPartner", Depends(authenticated_partner)],
):        
    author = env["support.task.api.helper"]._get_partner(partner, data.author.model_dump())
    domain = [("res_id", "=", data.id), ("model", "=", "project.task")]
    parent = env["mail.message"].search(
        domain + [("message_type", "=", "email")], order="id ASC", limit=1
    )
    if not parent:
        parent = env["mail.message"].search(domain, order="id ASC", limit=1)
    task = env["project.task"].browse(data.id)
    message = task.message_post(
        body=data.body,
        attachment_ids=[],
        parent_id=parent.id,
        subtype_xmlid="mail.mt_comment",
        author_id=author.id,
        message_type="comment",
        partner_ids=[],
        subject=_(""),
    )
    return message.id


@support_api_router.post(
    "/task/project_list",
)
def task_project_list(
    env: Annotated[api.Environment, Depends(authenticated_partner_env)],
    partner: Annotated["ResPartner", Depends(authenticated_partner)],
):        
    result = []
    helpdesk = partner.help_desk_project_id
    if helpdesk:
        result.append((helpdesk.id, helpdesk._get_customer_project_name()))
    projects = env["project.project"].search(
        [("partner_id", "=", partner.id), ("id", "!=", helpdesk.id), ("customer_display", "=", True)]
    )
    result += [(p.id, p._get_customer_project_name()) for p in projects]
    return result


@support_api_router.post(
    "/task/type_list",
)
def task_type_list(
    env: Annotated[api.Environment, Depends(authenticated_partner_env)],
    partner: Annotated["ResPartner", Depends(authenticated_partner)],
):        
    projects = partner.help_desk_project_id
    projects |= env["project.project"].search(
        [("partner_id", "=", partner.id), ("id", "!=", projects.id), ("customer_display", "=", True)]
    )
    tags = env["project.tags"]
    for project in projects:
        tags |= project.tag_ids
    return [(tag.id, tag.name) for tag in tags]


class SupportTaskApiHelper(models.AbstractModel):
    _name = "support.task.api.helper"
    _description = "Support api task helper"

    def _map_partner_read_to_data(self, partner_read):
        # partner_read is normally a tuple (id, name) but message_format return
        # a dict {"id": X, 'name', 'YY'} or even a list [('clear'),] if empty
        if not partner_read or (isinstance(partner_read, tuple) and not partner_read[0]) or isinstance(partner_read, list):
            # partner_read[0] can have the value 0 when their is not
            # partner linked to the message
            return False
        else:
            _id = isinstance(partner_read, tuple) and partner_read[0] or partner_read["id"]
            partner = self.env["res.partner"].browse(_id)
            if partner.customer_uid:
                return {
                    "type": "customer",
                    "vals": (partner.customer_uid, partner.name),
                }
            elif partner.user_ids:
                update_date = partner.write_date or partner.create_date
                return {
                    "type": "support",
                    "uid": partner.id,
                    "update_date": fields.Datetime.to_string(update_date),
                }
            else:
                return {"type": "anonymous", "vals": (0, partner.name)}

    def _get_all_project_ids_from_domain(self, partner, domain):
        # Note we apply a filter on a project we will always
        # show all stage of this project
        # this is not a perfect solution aand will not work with
        # advanced filtering on client side
        all_project_ids = (
            self.env["project.project"]
            .search([("partner_id", "=", partner.id)])
            .ids
        )
        project_ids = []
        for elem in domain:
            if len(elem) == 3 and elem[0] == "project_id" and elem[1] == "=":
                if elem[2] in all_project_ids:
                    project_ids.append(elem[2])
        return project_ids

    def _get_partner(self, partner, data):
        domain = [("parent_id", "=", partner.id)]
        if data.get("email"):
            domain += [
                "|",
                ("customer_uid", "=", data["uid"]),
                ("email", "=", data["email"]),
            ]
        else:
            domain += [("customer_uid", "=", data["uid"])]
        found_partner = self.env["res.partner"].search(domain)
        if not found_partner:
            found_partner = self.env["res.partner"].create(
                {
                    "parent_id": partner.id,
                    "image_1920": data["image"],
                    "name": data["name"],
                    "customer_uid": data["uid"],
                    "email": data["email"],
                    "mobile": data["mobile"],
                    "phone": data["phone"],
                }
            )
        elif (
            found_partner.name != data["name"]
            or found_partner.image_1920 != data["image"]
            or found_partner.email != data["email"]
            or found_partner.mobile != data["mobile"]
        ):
            _logger.debug("Update partner information")
            found_partner.write(
                {
                    "name": data["name"],
                    "image_1920": data["image"],
                    "email": data["email"],
                    "mobile": data["mobile"],
                    "phone": data["phone"],
                    "customer_uid": data["uid"],
                }
            )
        return found_partner

    def _manage_attachment_vals(self, vals):
        # Replace field name for write because attachment_ids already exists natively
        if "attachment_ids" in vals:
            # compatibility with client version 12 and before
            for attachment_command in vals["attachment_ids"]:
                if attachment_command[0] in (0, 1):
                    attachment_vals = attachment_command[2]
                    attachment_vals.pop("datas_fname", None)
            vals["support_attachment_ids"] = vals.pop("attachment_ids")
        return vals

    def message_format(self, partner, ids):
        allowed_task_ids = (
            self.env["project.task"]
            .search([("project_id.partner_id", "=", partner.id), ("project_id.customer_display", "=", True)])
            .ids
        )
        messages = self.env["mail.message"].browse(ids).message_format()
        if messages:
            for message in messages:
                if (
                    message["model"] != "project.task"
                    or message["res_id"] not in allowed_task_ids
                ):
                    raise AccessError(_("You can not read this message"))
                else:
                    message.update({"model": "external.task", "id": message["id"]})
                    message["author_id"] = self._map_partner_read_to_data(
                        message["author"]
                    )
                if "date" in message:
                    message["date"] = fields.Datetime.to_string(message["date"])
            return messages
        return []
