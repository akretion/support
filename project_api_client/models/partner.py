# -*- coding: utf-8 -*-
# Copyright 2018 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    support_uid = fields.Char()
    support_last_update_date = fields.Datetime()

    _sql_constraints = [
        ("support_uid_uniq", "unique (support_uid)", "Support UID already exist !")
    ]

    def _get_support_partner_vals(self, data):
        if "image" not in data:
            # in case that we have partial data we retrieve the full one
            data = self.env["support.account"]._call_odoo(
                "partner", "read", {"uid": data["uid"]}
            )
        return {
            "name": data["name"],
            "support_last_update_date": data["update_date"],
            "image": data["image"],
            "support_uid": data["uid"],
            "parent_id": self.env.ref("project_api_client.support_team").id,
            "company_id": False,
        }

    def _get_support_partner(self, data):
        """ This method will return the local partner used for the support
        If the partner is missing it will be created
        If the partner information are obsolete their will be updated"""
        self = self.with_context(bin_size=False)
        partner = self.env["res.partner"].search(
            [("support_uid", "=", str(data["uid"]))]
        )
        if not partner:
            vals = self._get_support_partner_vals(data)
            partner = self.env["res.partner"].create(vals)
        elif partner.support_last_update_date < data["update_date"]:
            vals = self._get_support_partner_vals(data)
            partner.write(vals)
        return partner

    def _get_local_id_name(self, data):
        """Return a tupple (id, name) of the partner
        In case of support partner return local data
        and update them if necessary
        """
        if not data:
            return False
        elif data["type"] in ("customer", "anonymous"):
            return data["vals"]
        else:
            partner = self._get_support_partner(data)
            return (partner.id, partner.name)
