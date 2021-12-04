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
            [("project_id.partner_id", "=", self.partner.id)]
        )
        attachments = self.env["ir.attachment"].search(
            [
                ("id", "in", ids),
                ("res_id", "in", tasks.ids),
                ("res_model", "=", "project.task"),
            ]
        )
        attachments = attachments.read(fields=fields, load=load)
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
