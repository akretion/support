# Copyright 2016 Akretion (http://www.akretion.com)
# Benoit Guillot <benoit.guillot@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging

import requests

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError

from odoo.addons.base_sparse_field.models.fields import Serialized

_logger = logging.getLogger(__name__)

ERROR_MESSAGE = _("There is an issue with support. Please send an email")


class SupportAccount(models.Model):
    _name = "support.account"
    _description = "Support account"

    name = fields.Char(required=True)
    url = fields.Char(required=True)
    api_key = fields.Char(required=True)
    company_id = fields.Many2one(comodel_name="res.company")
    state = fields.Selection(
        [("not_confirmed", "Not Confirmed"), ("confirmed", "Confirmed")],
        default="not_confirmed",
    )
    config = Serialized()

    def _create_or_update(self, model_name, vals):
        model = self.env[model_name]
        record = model.browse(vals["id"])
        if record.exists():
            vals.pop("id")
            record.write(vals)
        else:
            record = model._create([{
                "stored": vals,
                "inherited": {},
                "protected": {},
                }])

    def _sync_configuration(self):
        self.config = self._process_call_odoo("connection", "config", {})
        for project in self.config["projects"]:
            for vals in project["tags"]:
                self._create_or_update("o2o.project.tag", vals)
            for vals in project["stages"]:
                self._create_or_update("o2o.project.task.stage", vals)

    def _sync_support_partner(self):
        for support_uid in self._process_call_odoo("partner", "search"):
            data = self._process_call_odoo("partner", "read", {"uid": support_uid})
            self.env["res.partner"]._get_support_partner(data)
        return True

    def confirm_connection(self):
        try:
            self._process_call_odoo("connection", "test")
        except Exception as e:
            raise UserError(_("Fail to connect, %s") % e)
        self.state = "confirmed"
        self._sync_support_partner()
        self.sudo()._sync_configuration()
        return True

    def unconfirm_connection(self):
        self.state = "not_confirmed"
        return True

    def _get(self):
        return self.sudo().browse(self._get_id_for_company(self.env.user.company_id.id))

    @tools.ormcache("company_id")
    def _get_id_for_company(self, company_id):
        for c_id in [company_id, False]:
            account = self.sudo().search(
                [("company_id", "=", c_id), ("state", "=", "confirmed")]
            )
            if account:
                return account.id
        return False

    def _get_config(self):
        return self._get_config_for_company(self.env.user.company_id.id)

    @tools.ormcache("company_id")
    def _get_config_for_company(self, company_id):
        account_id = self._get_id_for_company(company_id)
        account = self.sudo().browse(account_id)
        return account.config

    def _clear_account_cache(self):
        self._get_id_for_company.clear_cache(self.env[self._name])
        self._get_config_for_company.clear_cache(self.env[self._name])

    @api.model
    def create(self, vals):
        self._clear_account_cache()
        return super(SupportAccount, self).create(vals)

    def write(self, vals):
        self._clear_account_cache()
        return super(SupportAccount, self).write(vals)

    def _call_odoo(self, path, method, params):
        account = self._get()
        return account._process_call_odoo(path, method, params)

    @api.model
    def _process_call_odoo(self, path, method, params=None):
        url = "{}/project-api/{}/{}".format(self.url, path, method)
        headers = {"API-KEY": self.api_key, "VERSION": "2.0"}
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
