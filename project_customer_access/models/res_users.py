# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo import api, models


class ResUsers(models.Model):
    _inherit = "res.users"

    def _get_support_partner_domain(self):
        """Domain of the partners visible by a customer user (used by the record
        rule on res.partner): the partners of the users sharing the same
        cross-connect client (i.e. the members of his company), the internal
        users (internal users without cross-connect client, needed to display
        the assignees / authors / followers of the tasks) and the customer
        partners of the projects of this client, plus his commercial partner, the
        companies and OdooBot.

        The relations are traversed by SQL, so the domain stays up to date when
        users/projects change. Users without a cross-connect client are not
        restricted.
        """
        self.ensure_one()
        client = self.cross_connect_client_id
        if not client:
            return [(1, "=", 1)]
        return [
            "|",
            "|",
            "|",
            "|",
            "|",
            "|",
            ("user_ids.cross_connect_client_id", "in", client.ids),
            "&",
            ("user_ids.groups_id", "in", [self.env.ref("base.group_user").id]),
            ("user_ids.cross_connect_client_id", "=", False),
            ("project_ids.cross_connect_client_id", "in", client.ids),
            ("task_ids.project_id.cross_connect_client_id", "in", client.ids),
            ("id", "=", self.commercial_partner_id.id),
            ("id", "in", self.company_ids.partner_id.ids),
            ("id", "=", self.env.ref("base.partner_root").id),
        ]

    @api.depends("cross_connect_client_id")
    def _compute_display_name(self):
        return super()._compute_display_name()

    def name_get(self):
        result = []
        standard_names = super().name_get()
        name_dict = dict(standard_names)

        # avoid to give rights on cross_connect_client
        for user in self.sudo():
            name = name_dict.get(user.id)
            # Si l'utilisateur a un serveur, on modifie le nom
            if user.cross_connect_client_id:
                name = f"{name} ({user.cross_connect_client_id.name})"
            result.append((user.id, name))
        return result
