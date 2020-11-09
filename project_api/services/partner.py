# -*- coding: utf-8 -*-
# Copyright 2019 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# pylint: disable=W8106
# pylint: disable=consider-merging-classes-inherited

import logging
import base64
from odoo.exceptions import AccessError
from odoo.tools.translate import _
from odoo import fields
import json

from odoo.addons.component.core import Component

_logger = logging.getLogger(__name__)


class ExternalTaskService(Component):
    _inherit = "base.rest.service"
    _name = "external.partner.service"
    _collection = "project.project"
    _usage = "partner"

    def search(self):
        return (
            self.env["res.partner"]
            .sudo()
            .search([("user_ids.active", "=", True), ("user_ids.share", "=", False)])
            .ids
        )

    def read(self, uid):
        """All res.user are exposed to this read only api"""
        partner = self.env["res.partner"].browse(uid)
        if partner.sudo().user_ids:
            image = partner.image
            image = base64.b64encode(image)
            update_date = partner.write_date or partner.create_date
            res = {
                "name": partner.name,
                "uid": uid,
                "image": image.decode(),
                "update_date": fields.Datetime.to_string(update_date),
            }
            return res
        else:
            raise AccessError(_("You can not read information about this partner"))

    def _validator_read(self):
        return {"uid": {"type": "integer"}}

    def _validator_search(self):
        return {}
