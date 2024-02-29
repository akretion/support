# Copyright 2019 Akretion (http://www.akretion.com).
# @author Mourad EL HADJ MIMOUNE <mourad.el.hadj.mimoune@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# pylint: disable=consider-merging-classes-inherited

from odoo import fields as odoo_fields

from odoo.addons.component.core import Component


class ExternalAttachmentService(Component):
    _inherit = "base.rest.service"
    _name = "external.attachment.service"
    _collection = "project.project"
    _usage = "attachment"

    @property
    def partner(self):
        return self.work.partner

    # pylint: disable=W8106
    def read(self, ids, fields, load):
        tasks = self.env["project.task"].search(
            [("project_id.partner_id", "=", self.partner.id), ("project_id.customer_display", "=", True)]
        )
        # compatibility with project_api_client <= 12
        # we could maybe remove datas_fname from all api_client version instead
        # maybe for next version
        if "datas_fname" in fields:
            if not "name" in fields:
                fields.append("name")
            fields.remove("datas_fname")
        attachments = self.env["ir.attachment"].search(
            [
                ("id", "in", ids),
                ("res_id", "in", tasks.ids),
                ("res_model", "=", "project.task"),
            ]
        )
        attachments = attachments.read(fields=fields, load=load)
        for attachment in attachments:
            if attachment.get("name"):
                attachment["datas_fname"] = attachment["name"]
        if attachments:
            for attachment in attachments:
                if "datas" in attachment:
                    attachment["datas"] = attachment["datas"].decode("utf-8")
                for date_field in ["write_date", "create_date"]:
                    if date_field in attachment:
                        attachment[date_field] = odoo_fields.Datetime.to_string(
                            attachment[date_field]
                        )
            return attachments
        return []

    def exists(self, ids):
        return self.env["ir.attachment"].browse(ids).exists().ids

    # Validator
    def _validator_read(self):
        return {
            "ids": {"type": "list"},
            "fields": {"type": "list"},
            "load": {"type": "string"},
            "context": {"type": "dict"},
        }

    def _validator_exists(self):
        return {"ids": {"type": "list"}}

    # Used since v16 on client side.
    def download_url(self, attachment_id):
        tasks = self.env["project.task"].search(
            [("project_id.partner_id", "=", self.partner.id), ("project_id.customer_display", "=", True)]
        )
        attachment = self.env["ir.attachment"].search(
            [
                ("id", "=", attachment_id),
                ("res_id", "in", tasks.ids),
                ("res_model", "=", "project.task"),
            ]
        )
        if not attachment:
            url = ""
        else:
            base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
            token = attachment.generate_access_token()[0]
            url = ("%(base_url)s/web/content/?id=%(attach_id)s&download=true"
                  "&filename=%(filename)s&access_token=%(token)s") % {"base_url": base_url, "attach_id": attachment_id, "filename": attachment.name, "token": token}
        return url

    def _validator_download_url(self):
        return {
            "attachment_id": {"type": "integer"},
            "context": {"type": "dict"},
        }
