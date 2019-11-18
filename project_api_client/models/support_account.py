# -*- coding: utf-8 -*-
# Copyright 2016 Akretion (http://www.akretion.com)
# Benoit Guillot <benoit.guillot@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ERROR_MESSAGE = _("There is an issue with support. Please send an email")


class SupportAccount(models.Model):
    _name = "support.account"
    _description = "Support account"

    name = fields.Char()
    url = fields.Char()
    api_key = fields.Char()
    company_id = fields.Many2one(comodel_name="res.company")

    # TODO cache me
    def _get(self):
        account = self.sudo().search([("company_id", "=", self.env.user.company_id.id)])
        if not account:
            account = self.sudo().search([("company_id", "=", False)])
        return account

    @api.model
    def _call_odoo(self, path, method, params):
        account = self._get()
        url = "{}/project-api/{}/{}".format(account.url, path, method)
        headers = {"API-KEY": account.api_key}
        try:
            res = requests.post(url, headers=headers, json=params)
        except Exception as e:
            _logger.error("Error when calling odoo %s", e)
            raise UserError(ERROR_MESSAGE)
        data = res.json()
        if isinstance(data, dict) and data.get("code", 0) >= 400:
            _logger.error(
                "Error Support API : %s : %s", data.get("name"), data.get("description")
            )
            raise UserError(ERROR_MESSAGE)
        return data
